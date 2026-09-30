import 'dart:async';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../config/theme.dart';
import '../../models/integration_models.dart';
import '../../providers/integration_provider.dart';
import '../../utils/popup_helper.dart';
import '../../widgets/glass_card.dart';
import '../../widgets/skeleton_loader.dart';

class IntegrationsScreen extends StatefulWidget {
  const IntegrationsScreen({super.key});

  @override
  State<IntegrationsScreen> createState() => _IntegrationsScreenState();
}

class _IntegrationsScreenState extends State<IntegrationsScreen> {
  final _imapServerController = TextEditingController();
  final _imapPortController = TextEditingController(text: '993');
  final _imapUsernameController = TextEditingController();
  final _imapPasswordController = TextEditingController();
  bool _obscurePassword = true;

  Process? _activeOAuthProcess;

  void _closeOAuthWindow() {
    try {
      _activeOAuthProcess?.kill();
      _activeOAuthProcess = null;
      if (!kIsWeb && Platform.isLinux) {
        Process.run('pkill', ['-f', 'sakshi_zoho_auth']);
      }
    } catch (_) {}
  }

  Future<void> _openExternalUrl(String url, ScaffoldMessengerState scaffoldMessenger) async {
    final uri = Uri.parse(url);
    bool success = false;

    // Web Application: Open as mini application-style popup window in browser
    if (kIsWeb) {
      try {
        openWebPopupWindow(url);
        success = true;
      } catch (_) {
        success = false;
      }
    }

    // Linux Desktop: Open as standalone mini Chrome application window
    if (!kIsWeb && Platform.isLinux) {
      try {
        _closeOAuthWindow();
        _activeOAuthProcess = await Process.start('google-chrome', [
          '--user-data-dir=/tmp/sakshi_zoho_auth',
          '--app=$url',
          '--window-size=640,800',
          '--window-position=300,100',
          '--no-first-run',
          '--no-default-browser-check',
        ]);
        success = true;
      } catch (_) {
        try {
          _activeOAuthProcess = await Process.start('google-chrome-stable', [
            '--user-data-dir=/tmp/sakshi_zoho_auth',
            '--app=$url',
            '--window-size=640,800',
            '--window-position=300,100',
            '--no-first-run',
            '--no-default-browser-check',
          ]);
          success = true;
        } catch (_) {}
      }
    }

    if (!success) {
      try {
        success = await launchUrl(uri, mode: LaunchMode.externalApplication);
      } catch (_) {
        success = false;
      }
    }

    if (!success && !kIsWeb) {
      try {
        if (Platform.isLinux) {
          await Process.run('xdg-open', [url]);
          success = true;
        } else if (Platform.isWindows) {
          await Process.run('start', [url], runInShell: true);
          success = true;
        } else if (Platform.isMacOS) {
          await Process.run('open', [url]);
          success = true;
        }
      } catch (_) {}
    }

    if (!success) {
      await Clipboard.setData(ClipboardData(text: url));
      scaffoldMessenger.showSnackBar(
        SnackBar(
          content: Text('OAuth Link copied to clipboard: $url'),
          backgroundColor: AppTheme.accentColor,
        ),
      );
    }
  }

  static const List<Map<String, String>> _zohoRegions = [
    {
      'id': 'in',
      'label': 'India (.IN)',
      'url': 'https://accounts.zoho.in',
      'flag': '🇮🇳',
      'desc': 'For Indian business entities, GST compliance, and Zoho India accounts',
    },
    {
      'id': 'com',
      'label': 'United States / Global (.COM)',
      'url': 'https://accounts.zoho.com',
      'flag': '🇺🇸',
      'desc': 'For North America and international global Zoho accounts',
    },
    {
      'id': 'eu',
      'label': 'Europe (.EU)',
      'url': 'https://accounts.zoho.eu',
      'flag': '🇪🇺',
      'desc': 'For European Union organizations and GDPR data residency',
    },
    {
      'id': 'au',
      'label': 'Australia (.COM.AU)',
      'url': 'https://accounts.zoho.com.au',
      'flag': '🇦🇺',
      'desc': 'For Australian and New Zealand business organizations',
    },
  ];

  void _startAutomaticZohoAuth() {
    final scaffoldMessenger = ScaffoldMessenger.of(context);
    final intProvider = Provider.of<IntegrationProvider>(context, listen: false);

    String selectedRegionId = intProvider.selectedDataCenter;
    String selectedAccountsUrl = _zohoRegions.firstWhere(
      (r) => r['id'] == selectedRegionId,
      orElse: () => _zohoRegions.first,
    )['url']!;

    int currentStep = 1; // 1: Region Selection, 2: Active OAuth Authentication
    String authUrl = '';
    Timer? pollTimer;
    bool isModalOpen = true;

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (dialogCtx) {
        final theme = Theme.of(dialogCtx);
        final isDark = theme.brightness == Brightness.dark;

        return StatefulBuilder(
          builder: (context, setModalState) {
            final isConnected = intProvider.zohoStatus.isConnected;

            Future<void> proceedToOAuth() async {
              intProvider.setDataCenter(selectedRegionId);
              setModalState(() {
                currentStep = 2;
              });

              try {
                authUrl = await intProvider.getZohoAuthUrl(accountsUrl: selectedAccountsUrl);
                if (authUrl.isNotEmpty) {
                  _openExternalUrl(authUrl, scaffoldMessenger);
                }
              } catch (e) {
                if (context.mounted) {
                  scaffoldMessenger.showSnackBar(
                    SnackBar(
                      content: Text('Failed to initiate Zoho connection: ${e.toString().replaceAll("Exception: ", "")}'),
                      backgroundColor: AppTheme.errorColor,
                    ),
                  );
                  setModalState(() {
                    currentStep = 1;
                  });
                }
                return;
              }

              // Auto-poll loop every 1.0 second
              pollTimer?.cancel();
              pollTimer = Timer.periodic(const Duration(milliseconds: 1000), (timer) async {
                if (!isModalOpen || !mounted) {
                  timer.cancel();
                  return;
                }

                await intProvider.fetchStatus();
                if (intProvider.zohoStatus.isConnected) {
                  timer.cancel();
                  _closeOAuthWindow();
                  await intProvider.fetchOrganizations();
                  await intProvider.fetchZohoMasterData();
                  if (intProvider.masterAccounts.isEmpty || intProvider.zohoStatus.accountsCount == 0) {
                    intProvider.syncZohoNow();
                  }

                  if (mounted && isModalOpen) {
                    setModalState(() {});
                    scaffoldMessenger.showSnackBar(
                      SnackBar(
                        content: Text('Zoho Books Connected: ${intProvider.zohoStatus.organizationName ?? "Authorized"} — Syncing master data...'),
                        backgroundColor: AppTheme.accentColor,
                      ),
                    );
                    await Future.delayed(const Duration(milliseconds: 1200));
                    if (mounted && isModalOpen && dialogCtx.mounted) {
                      Navigator.of(dialogCtx).pop();
                    }
                  }
                }
              });
            }

            return AlertDialog(
              backgroundColor: isDark ? const Color(0xFF0F172A) : Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
              titlePadding: const EdgeInsets.fromLTRB(24, 22, 24, 12),
              contentPadding: const EdgeInsets.fromLTRB(24, 0, 24, 20),
              actionsPadding: const EdgeInsets.fromLTRB(24, 0, 24, 20),
              title: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(9),
                    decoration: BoxDecoration(
                      color: AppTheme.primaryColor.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Icon(
                      currentStep == 1 ? Icons.public_rounded : Icons.hub_rounded,
                      color: AppTheme.primaryColor,
                      size: 22,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      currentStep == 1 ? 'Select Zoho Geographic Region' : 'Connecting Zoho Books',
                      style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
                    ),
                  ),
                ],
              ),
              content: SizedBox(
                width: 480,
                child: currentStep == 1
                    ? Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Select the geographic data center where your Zoho Books organization is hosted:',
                            style: TextStyle(fontSize: 12.5, color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
                          ),
                          const SizedBox(height: 16),
                          ..._zohoRegions.map((region) {
                            final isSelected = selectedRegionId == region['id'];

                            return Container(
                              margin: const EdgeInsets.only(bottom: 8),
                              decoration: BoxDecoration(
                                color: isSelected
                                    ? AppTheme.primaryColor.withValues(alpha: isDark ? 0.18 : 0.08)
                                    : (isDark ? const Color(0xFF1E293B).withValues(alpha: 0.5) : const Color(0xFFF8FAFC)),
                                borderRadius: BorderRadius.circular(12),
                                border: Border.all(
                                  color: isSelected
                                      ? AppTheme.primaryColor
                                      : (isDark ? const Color(0xFF334155) : const Color(0xFFE2E8F0)),
                                  width: isSelected ? 1.5 : 1.0,
                                ),
                              ),
                              child: Material(
                                color: Colors.transparent,
                                child: InkWell(
                                  borderRadius: BorderRadius.circular(12),
                                  onTap: () {
                                    setModalState(() {
                                      selectedRegionId = region['id']!;
                                      selectedAccountsUrl = region['url']!;
                                    });
                                  },
                                  child: Padding(
                                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                                    child: Row(
                                      children: [
                                        Text(region['flag']!, style: const TextStyle(fontSize: 22)),
                                        const SizedBox(width: 12),
                                        Expanded(
                                          child: Column(
                                            crossAxisAlignment: CrossAxisAlignment.start,
                                            children: [
                                              Text(
                                                region['label']!,
                                                style: TextStyle(
                                                  fontSize: 13.5,
                                                  fontWeight: isSelected ? FontWeight.w700 : FontWeight.w600,
                                                  color: isDark ? Colors.white : const Color(0xFF0F172A),
                                                ),
                                              ),
                                              const SizedBox(height: 2),
                                              Text(
                                                region['desc']!,
                                                style: TextStyle(
                                                  fontSize: 11,
                                                  color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B),
                                                ),
                                              ),
                                            ],
                                          ),
                                        ),
                                        AnimatedContainer(
                                          duration: const Duration(milliseconds: 200),
                                          width: 20,
                                          height: 20,
                                          decoration: BoxDecoration(
                                            shape: BoxShape.circle,
                                            border: Border.all(
                                              color: isSelected ? AppTheme.primaryColor : (isDark ? const Color(0xFF64748B) : const Color(0xFF94A3B8)),
                                              width: isSelected ? 6 : 2,
                                            ),
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                              ),
                            );
                          }),
                        ],
                      )
                    : Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          if (!isConnected) ...[
                            const SizedBox(height: 12),
                            const SizedBox(
                              height: 40,
                              width: 40,
                              child: CircularProgressIndicator(strokeWidth: 3),
                            ),
                            const SizedBox(height: 20),
                            Text(
                              'Redirected to Zoho in Chrome ($selectedAccountsUrl)...',
                              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                              textAlign: TextAlign.center,
                            ),
                            const SizedBox(height: 8),
                            const Text(
                              'Please enter your Zoho credentials and click "Accept" in the opened browser window. This app will automatically detect approval and bring you back immediately.',
                              textAlign: TextAlign.center,
                              style: TextStyle(fontSize: 12.5, color: Colors.grey, height: 1.4),
                            ),
                            const SizedBox(height: 20),
                            OutlinedButton.icon(
                              onPressed: () {
                                if (authUrl.isNotEmpty) {
                                  _openExternalUrl(authUrl, scaffoldMessenger);
                                }
                              },
                              icon: const Icon(Icons.open_in_browser_rounded, size: 16),
                              label: const Text('Re-open Authorization Tab'),
                            ),
                          ] else ...[
                            const SizedBox(height: 8),
                            const Icon(Icons.check_circle_rounded, color: AppTheme.accentColor, size: 52),
                            const SizedBox(height: 16),
                            const Text(
                              'Zoho Books Connected Successfully!',
                              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: AppTheme.accentColor),
                              textAlign: TextAlign.center,
                            ),
                            const SizedBox(height: 6),
                            Text(
                              'Connected as: ${intProvider.zohoStatus.organizationName ?? "Primary Organization"}',
                              textAlign: TextAlign.center,
                              style: const TextStyle(fontSize: 13),
                            ),
                          ],
                        ],
                      ),
              ),
              actions: [
                if (currentStep == 1) ...[
                  TextButton(
                    onPressed: () {
                      isModalOpen = false;
                      pollTimer?.cancel();
                      _closeOAuthWindow();
                      if (dialogCtx.mounted) {
                        Navigator.of(dialogCtx).pop();
                      }
                    },
                    child: const Text('Cancel'),
                  ),
                  ElevatedButton.icon(
                    onPressed: proceedToOAuth,
                    icon: const Icon(Icons.arrow_forward_rounded, size: 16),
                    label: const Text('Proceed to Zoho Login'),
                  ),
                ] else if (!isConnected) ...[
                  TextButton(
                    onPressed: () {
                      pollTimer?.cancel();
                      _closeOAuthWindow();
                      setModalState(() {
                        currentStep = 1;
                      });
                    },
                    child: const Text('Change Region'),
                  ),
                  TextButton(
                    onPressed: () async {
                      await intProvider.fetchStatus();
                      setModalState(() {});
                    },
                    child: const Text('Check Status'),
                  ),
                  TextButton(
                    onPressed: () {
                      isModalOpen = false;
                      pollTimer?.cancel();
                      _closeOAuthWindow();
                      if (dialogCtx.mounted) {
                        Navigator.of(dialogCtx).pop();
                      }
                    },
                    child: const Text('Cancel'),
                  ),
                ] else ...[
                  ElevatedButton(
                    onPressed: () {
                      isModalOpen = false;
                      pollTimer?.cancel();
                      _closeOAuthWindow();
                      if (dialogCtx.mounted) {
                        Navigator.of(dialogCtx).pop();
                      }
                    },
                    child: const Text('Done'),
                  ),
                ],
              ],
            );
          },
        );
      },
    ).then((_) {
      isModalOpen = false;
      pollTimer?.cancel();
      _closeOAuthWindow();
    });
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (!mounted) return;
      final intProvider = Provider.of<IntegrationProvider>(context, listen: false);
      await intProvider.fetchStatus();
      intProvider.fetchOrganizations();
      if (intProvider.zohoStatus.isConnected) {
        await intProvider.fetchZohoMasterData();
        if (intProvider.masterAccounts.isEmpty && intProvider.zohoStatus.accountsCount == 0) {
          intProvider.syncZohoNow();
        }
      }
      if (!mounted) return;
      _imapServerController.text = intProvider.emailConfig.imapServer ?? 'imap.gmail.com';
      _imapPortController.text = (intProvider.emailConfig.imapPort ?? 993).toString();
      _imapUsernameController.text = intProvider.emailConfig.username ?? '';
    });
  }

  @override
  void dispose() {
    _imapServerController.dispose();
    _imapPortController.dispose();
    _imapUsernameController.dispose();
    _imapPasswordController.dispose();
    super.dispose();
  }

  Color _getAccountTypeColor(String? type, bool isDark) {
    switch (type?.toLowerCase()) {
      case 'expense':
      case 'other_expense':
      case 'cost_of_goods_sold':
        return Colors.orangeAccent;
      case 'income':
      case 'other_income':
        return Colors.greenAccent;
      case 'fixed_asset':
      case 'other_current_asset':
      case 'bank':
      case 'cash':
        return Colors.lightBlueAccent;
      case 'other_current_liability':
      case 'accounts_payable':
      case 'long_term_liability':
        return Colors.pinkAccent;
      case 'equity':
        return Colors.purpleAccent;
      default:
        return isDark ? Colors.grey : Colors.blueGrey;
    }
  }

  void _showChartOfAccountsDialog(BuildContext context) {
    final intProvider = Provider.of<IntegrationProvider>(context, listen: false);
    if (intProvider.masterAccounts.isEmpty) {
      intProvider.fetchZohoMasterData();
    }

    showDialog(
      context: context,
      builder: (ctx) {
        String searchQuery = '';
        String selectedType = 'All';

        return StatefulBuilder(
          builder: (dialogCtx, setDialogState) {
            final theme = Theme.of(dialogCtx);
            final isDark = theme.brightness == Brightness.dark;
            final provider = Provider.of<IntegrationProvider>(dialogCtx);
            final accounts = provider.masterAccounts;
            final isLoading = provider.isLoadingMasterData;

            final filteredAccounts = accounts.where((acc) {
              if (selectedType != 'All' && (acc.type?.toLowerCase() != selectedType.toLowerCase())) {
                return false;
              }
              if (searchQuery.isNotEmpty) {
                final q = searchQuery.toLowerCase();
                final nameMatch = acc.name.toLowerCase().contains(q);
                final codeMatch = (acc.code?.toLowerCase() ?? '').contains(q);
                final typeMatch = (acc.type?.toLowerCase() ?? '').contains(q);
                return nameMatch || codeMatch || typeMatch;
              }
              return true;
            }).toList();

            return Dialog(
              backgroundColor: isDark ? const Color(0xFF0F172A) : Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 800, maxHeight: 680),
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Header
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: AppTheme.primaryColor.withValues(alpha: 0.12),
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: const Icon(Icons.account_tree_outlined, color: AppTheme.primaryColor, size: 24),
                          ),
                          const SizedBox(width: 14),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    const Text('Chart of Accounts', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                                    const SizedBox(width: 10),
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                      decoration: BoxDecoration(
                                        color: AppTheme.primaryColor.withValues(alpha: 0.15),
                                        borderRadius: BorderRadius.circular(6),
                                      ),
                                      child: Text(
                                        '${accounts.length} Accounts',
                                        style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: AppTheme.primaryColor),
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  'Synced from Zoho Books: ${provider.zohoStatus.organizationName ?? "Primary Org"}',
                                  style: TextStyle(fontSize: 12, color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
                                ),
                              ],
                            ),
                          ),
                          IconButton(
                            tooltip: 'Refresh Master Data',
                            icon: const Icon(Icons.refresh_rounded),
                            onPressed: () => provider.fetchZohoMasterData(),
                          ),
                          IconButton(
                            icon: const Icon(Icons.close_rounded),
                            onPressed: () => Navigator.of(ctx).pop(),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),

                      // Search and Filter Bar
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              decoration: InputDecoration(
                                hintText: 'Search by account name, code, or type...',
                                prefixIcon: const Icon(Icons.search_rounded, size: 18),
                                isDense: true,
                                filled: true,
                                fillColor: isDark ? const Color(0xFF1E293B) : const Color(0xFFF1F5F9),
                                border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide.none),
                              ),
                              onChanged: (val) {
                                setDialogState(() => searchQuery = val);
                              },
                            ),
                          ),
                          const SizedBox(width: 12),
                          DropdownButtonHideUnderline(
                            child: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 12),
                              decoration: BoxDecoration(
                                color: isDark ? const Color(0xFF1E293B) : const Color(0xFFF1F5F9),
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: DropdownButton<String>(
                                value: selectedType,
                                items: const [
                                  DropdownMenuItem(value: 'All', child: Text('All Types')),
                                  DropdownMenuItem(value: 'expense', child: Text('Expense')),
                                  DropdownMenuItem(value: 'income', child: Text('Income')),
                                  DropdownMenuItem(value: 'fixed_asset', child: Text('Asset')),
                                  DropdownMenuItem(value: 'other_current_liability', child: Text('Liability')),
                                  DropdownMenuItem(value: 'equity', child: Text('Equity')),
                                ],
                                onChanged: (val) {
                                  if (val != null) {
                                    setDialogState(() => selectedType = val);
                                  }
                                },
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),

                      // Account List
                      Expanded(
                        child: isLoading
                            ? const IntegrationMasterDataSkeleton()
                            : filteredAccounts.isEmpty
                                ? Center(
                                    child: Column(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Icon(Icons.search_off_rounded, size: 40, color: isDark ? Colors.grey[600] : Colors.grey[400]),
                                        const SizedBox(height: 10),
                                        const Text('No accounts match your filter', style: TextStyle(fontWeight: FontWeight.bold)),
                                      ],
                                    ),
                                  )
                                : ListView.separated(
                                    itemCount: filteredAccounts.length,
                                    separatorBuilder: (context, index) => const Divider(height: 1),
                                    itemBuilder: (context, index) {
                                      final acc = filteredAccounts[index];
                                      final typeColor = _getAccountTypeColor(acc.type, isDark);

                                      return ListTile(
                                        dense: true,
                                        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                                        leading: Container(
                                          padding: const EdgeInsets.all(6),
                                          decoration: BoxDecoration(
                                            color: typeColor.withValues(alpha: 0.15),
                                            borderRadius: BorderRadius.circular(6),
                                          ),
                                          child: Icon(Icons.bookmark_outline_rounded, color: typeColor, size: 16),
                                        ),
                                        title: Text(
                                          acc.name,
                                          style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                                        ),
                                        subtitle: Text(
                                          'Code: ${acc.code ?? "N/A"}  •  Zoho ID: ${acc.zohoAccountId ?? acc.id}',
                                          style: TextStyle(fontSize: 11, color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
                                        ),
                                        trailing: Container(
                                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                          decoration: BoxDecoration(
                                            color: typeColor.withValues(alpha: 0.15),
                                            borderRadius: BorderRadius.circular(6),
                                          ),
                                          child: Text(
                                            (acc.type ?? 'General').toUpperCase(),
                                            style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: typeColor),
                                          ),
                                        ),
                                      );
                                    },
                                  ),
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        );
      },
    );
  }

  void _showTaxesDialog(BuildContext context) {
    final intProvider = Provider.of<IntegrationProvider>(context, listen: false);
    if (intProvider.masterTaxes.isEmpty) {
      intProvider.fetchZohoMasterData();
    }

    showDialog(
      context: context,
      builder: (ctx) {
        String searchQuery = '';

        return StatefulBuilder(
          builder: (dialogCtx, setDialogState) {
            final theme = Theme.of(dialogCtx);
            final isDark = theme.brightness == Brightness.dark;
            final provider = Provider.of<IntegrationProvider>(dialogCtx);
            final taxes = provider.masterTaxes;
            final isLoading = provider.isLoadingMasterData;

            final filteredTaxes = taxes.where((tax) {
              if (searchQuery.isNotEmpty) {
                final q = searchQuery.toLowerCase();
                final nameMatch = tax.name.toLowerCase().contains(q);
                final typeMatch = (tax.type?.toLowerCase() ?? '').contains(q);
                final pctMatch = tax.percentage.toString().contains(q);
                return nameMatch || typeMatch || pctMatch;
              }
              return true;
            }).toList();

            return Dialog(
              backgroundColor: isDark ? const Color(0xFF0F172A) : Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 750, maxHeight: 650),
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Header
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: Colors.purple.withValues(alpha: 0.12),
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: const Icon(Icons.receipt_long_outlined, color: Colors.purple, size: 24),
                          ),
                          const SizedBox(width: 14),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    const Text('GST & TDS Tax Rates', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                                    const SizedBox(width: 10),
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                      decoration: BoxDecoration(
                                        color: Colors.purple.withValues(alpha: 0.15),
                                        borderRadius: BorderRadius.circular(6),
                                      ),
                                      child: Text(
                                        '${taxes.length} Tax Rates',
                                        style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.purple),
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  'Configured tax accounts & withholding rules in Zoho Books',
                                  style: TextStyle(fontSize: 12, color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
                                ),
                              ],
                            ),
                          ),
                          IconButton(
                            tooltip: 'Refresh Master Data',
                            icon: const Icon(Icons.refresh_rounded),
                            onPressed: () => provider.fetchZohoMasterData(),
                          ),
                          IconButton(
                            icon: const Icon(Icons.close_rounded),
                            onPressed: () => Navigator.of(ctx).pop(),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),

                      // Search Bar
                      TextField(
                        decoration: InputDecoration(
                          hintText: 'Search tax name, rate percentage (e.g. 18%), or type...',
                          prefixIcon: const Icon(Icons.search_rounded, size: 18),
                          isDense: true,
                          filled: true,
                          fillColor: isDark ? const Color(0xFF1E293B) : const Color(0xFFF1F5F9),
                          border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide.none),
                        ),
                        onChanged: (val) {
                          setDialogState(() => searchQuery = val);
                        },
                      ),
                      const SizedBox(height: 16),

                      // Tax List
                      Expanded(
                        child: isLoading
                            ? const IntegrationMasterDataSkeleton()
                            : filteredTaxes.isEmpty
                                ? Center(
                                    child: Column(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Icon(Icons.search_off_rounded, size: 40, color: isDark ? Colors.grey[600] : Colors.grey[400]),
                                        const SizedBox(height: 10),
                                        const Text('No tax rates found matching search', style: TextStyle(fontWeight: FontWeight.bold)),
                                      ],
                                    ),
                                  )
                                : ListView.separated(
                                    itemCount: filteredTaxes.length,
                                    separatorBuilder: (context, index) => const Divider(height: 1),
                                    itemBuilder: (context, index) {
                                      final tax = filteredTaxes[index];
                                      final isTds = (tax.type?.toLowerCase().contains('tds') ?? false) || tax.name.toLowerCase().contains('tds');

                                      return ListTile(
                                        dense: true,
                                        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                                        leading: Container(
                                          padding: const EdgeInsets.all(6),
                                          decoration: BoxDecoration(
                                            color: (isTds ? Colors.amber : Colors.purple).withValues(alpha: 0.15),
                                            borderRadius: BorderRadius.circular(6),
                                          ),
                                          child: Icon(
                                            isTds ? Icons.shield_outlined : Icons.percent_rounded,
                                            color: isTds ? Colors.amber : Colors.purple,
                                            size: 16,
                                          ),
                                        ),
                                        title: Text(
                                          tax.name,
                                          style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                                        ),
                                        subtitle: Text(
                                          'Type: ${tax.type ?? (isTds ? "TDS Withholding" : "GST Tax")}  •  Zoho ID: ${tax.zohoTaxId ?? tax.id}',
                                          style: TextStyle(fontSize: 11, color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
                                        ),
                                        trailing: Container(
                                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                                          decoration: BoxDecoration(
                                            color: AppTheme.accentColor.withValues(alpha: 0.15),
                                            borderRadius: BorderRadius.circular(6),
                                          ),
                                          child: Text(
                                            '${tax.percentage.toStringAsFixed(tax.percentage.truncateToDouble() == tax.percentage ? 0 : 2)}%',
                                            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.accentColor),
                                          ),
                                        ),
                                      );
                                    },
                                  ),
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        );
      },
    );
  }

  void _showVendorsDialog(BuildContext context) {
    final intProvider = Provider.of<IntegrationProvider>(context, listen: false);
    if (intProvider.masterVendors.isEmpty) {
      intProvider.fetchZohoMasterData();
    }

    showDialog(
      context: context,
      builder: (ctx) {
        String searchQuery = '';

        return StatefulBuilder(
          builder: (dialogCtx, setDialogState) {
            final theme = Theme.of(dialogCtx);
            final isDark = theme.brightness == Brightness.dark;
            final provider = Provider.of<IntegrationProvider>(dialogCtx);
            final vendors = provider.masterVendors;
            final isLoading = provider.isLoadingMasterData;

            final filteredVendors = vendors.where((v) {
              if (searchQuery.isNotEmpty) {
                final q = searchQuery.toLowerCase();
                final nameMatch = v.name.toLowerCase().contains(q);
                final gstinMatch = (v.gstin?.toLowerCase() ?? '').contains(q);
                final panMatch = (v.pan?.toLowerCase() ?? '').contains(q);
                return nameMatch || gstinMatch || panMatch;
              }
              return true;
            }).toList();

            return Dialog(
              backgroundColor: isDark ? const Color(0xFF0F172A) : Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 800, maxHeight: 680),
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Header
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: Colors.amber.withValues(alpha: 0.12),
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: const Icon(Icons.people_outline_rounded, color: Colors.amber, size: 24),
                          ),
                          const SizedBox(width: 14),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    const Text('Synced Vendors', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                                    const SizedBox(width: 10),
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                      decoration: BoxDecoration(
                                        color: Colors.amber.withValues(alpha: 0.15),
                                        borderRadius: BorderRadius.circular(6),
                                      ),
                                      child: Text(
                                        '${vendors.length} Vendors',
                                        style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.amber),
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  'Vendor directory with GSTIN & PAN mappings synced from Zoho Books',
                                  style: TextStyle(fontSize: 12, color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
                                ),
                              ],
                            ),
                          ),
                          IconButton(
                            tooltip: 'Refresh Master Data',
                            icon: const Icon(Icons.refresh_rounded),
                            onPressed: () => provider.fetchZohoMasterData(),
                          ),
                          IconButton(
                            icon: const Icon(Icons.close_rounded),
                            onPressed: () => Navigator.of(ctx).pop(),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),

                      // Search Bar
                      TextField(
                        decoration: InputDecoration(
                          hintText: 'Search by vendor name, GSTIN, or PAN...',
                          prefixIcon: const Icon(Icons.search_rounded, size: 18),
                          isDense: true,
                          filled: true,
                          fillColor: isDark ? const Color(0xFF1E293B) : const Color(0xFFF1F5F9),
                          border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide.none),
                        ),
                        onChanged: (val) {
                          setDialogState(() => searchQuery = val);
                        },
                      ),
                      const SizedBox(height: 16),

                      // Vendor List
                      Expanded(
                        child: isLoading
                            ? const IntegrationMasterDataSkeleton()
                            : filteredVendors.isEmpty
                                ? Center(
                                    child: Column(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Icon(Icons.person_search_rounded, size: 40, color: isDark ? Colors.grey[600] : Colors.grey[400]),
                                        const SizedBox(height: 10),
                                        const Text('No vendors found matching search', style: TextStyle(fontWeight: FontWeight.bold)),
                                      ],
                                    ),
                                  )
                                : ListView.separated(
                                    itemCount: filteredVendors.length,
                                    separatorBuilder: (context, index) => const Divider(height: 1),
                                    itemBuilder: (context, index) {
                                      final v = filteredVendors[index];

                                      return ListTile(
                                        dense: true,
                                        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                                        leading: CircleAvatar(
                                          backgroundColor: AppTheme.primaryColor.withValues(alpha: 0.12),
                                          child: Text(
                                            v.name.isNotEmpty ? v.name[0].toUpperCase() : 'V',
                                            style: const TextStyle(fontWeight: FontWeight.bold, color: AppTheme.primaryColor),
                                          ),
                                        ),
                                        title: Text(
                                          v.name,
                                          style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                                        ),
                                        subtitle: Row(
                                          children: [
                                            if (v.gstin != null && v.gstin!.isNotEmpty) ...[
                                              Text('GSTIN: ${v.gstin}', style: const TextStyle(fontSize: 11)),
                                              const SizedBox(width: 8),
                                            ],
                                            if (v.pan != null && v.pan!.isNotEmpty) ...[
                                              Text('PAN: ${v.pan}', style: const TextStyle(fontSize: 11)),
                                              const SizedBox(width: 8),
                                            ],
                                            Text(
                                              'ID: ${v.zohoContactId ?? v.id}',
                                              style: TextStyle(fontSize: 11, color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
                                            ),
                                          ],
                                        ),
                                        trailing: Container(
                                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                          decoration: BoxDecoration(
                                            color: AppTheme.accentColor.withValues(alpha: 0.15),
                                            borderRadius: BorderRadius.circular(6),
                                          ),
                                          child: Text(
                                            v.approvalStatus ?? 'ACTIVE',
                                            style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: AppTheme.accentColor),
                                          ),
                                        ),
                                      );
                                    },
                                  ),
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        );
      },
    );
  }

  Widget _buildMasterDataMetricTile({
    required String title,
    required int count,
    required IconData icon,
    required Color color,
    required VoidCallback onTap,
    required bool isDark,
  }) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(10),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
          decoration: BoxDecoration(
            color: isDark ? const Color(0xFF0F172A) : Colors.white,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: isDark ? const Color(0xFF334155) : const Color(0xFFE2E8F0)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Container(
                    padding: const EdgeInsets.all(5),
                    decoration: BoxDecoration(
                      color: color.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Icon(icon, color: color, size: 15),
                  ),
                  Icon(Icons.chevron_right_rounded, size: 14, color: isDark ? Colors.grey[600] : Colors.grey[400]),
                ],
              ),
              const SizedBox(height: 6),
              Text(
                '$count',
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 1),
              Text(
                title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(fontSize: 10.5, color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final intProvider = Provider.of<IntegrationProvider>(context);
    final zoho = intProvider.zohoStatus;
    final email = intProvider.emailConfig;
    final isEmailConnected = email.isConnected;
    final isMobile = MediaQuery.of(context).size.width < 650;

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: SingleChildScrollView(
        padding: EdgeInsets.symmetric(
          horizontal: isMobile ? 16 : 32,
          vertical: isMobile ? 18 : 28,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Integrations & Services',
              style: TextStyle(
                fontSize: isMobile ? 22 : 26,
                fontWeight: FontWeight.w800,
                letterSpacing: -0.6,
                color: isDark ? Colors.white : const Color(0xFF0F172A),
              ),
            ),
            const SizedBox(height: 4),
            Text(
              'Manage your accounting sync connectors, Zoho Books OAuth, and Email mailboxes',
              style: TextStyle(
                fontSize: isMobile ? 12.5 : 13.5,
                color: isDark ? AppTheme.darkTextSecondary : AppTheme.lightTextSecondary,
              ),
            ),
            const SizedBox(height: 20),
            LayoutBuilder(
              builder: (context, constraints) {
                final isWide = constraints.maxWidth >= 950;

                final zohoCard = GlassCard(
                  padding: EdgeInsets.all(isMobile ? 16 : 22),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: Row(
                              children: [
                                Container(
                                  padding: const EdgeInsets.all(10),
                                  decoration: BoxDecoration(
                                    color: AppTheme.primaryColor.withValues(alpha: 0.1),
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  child: const Icon(Icons.hub_outlined, color: AppTheme.primaryColor, size: 24),
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      const Text('Zoho Books ERP', style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold)),
                                      const SizedBox(height: 2),
                                      Text(
                                        zoho.isConnected
                                            ? 'Connected as ${zoho.organizationName ?? "Primary Org"}'
                                            : 'Bidirectional sync for bills',
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: TextStyle(fontSize: 11.5, color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: (zoho.isConnected ? AppTheme.accentColor : AppTheme.warningColor).withValues(alpha: 0.15),
                              borderRadius: BorderRadius.circular(20),
                              border: Border.all(
                                color: zoho.isConnected ? AppTheme.accentColor : AppTheme.warningColor,
                                width: 1,
                              ),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(
                                  zoho.isConnected ? Icons.check_circle_rounded : Icons.radio_button_unchecked_rounded,
                                  size: 13,
                                  color: zoho.isConnected ? AppTheme.accentColor : AppTheme.warningColor,
                                ),
                                const SizedBox(width: 4),
                                Text(
                                  zoho.isConnected ? 'Connected' : 'Disconnected',
                                  style: TextStyle(
                                    fontSize: 11,
                                    fontWeight: FontWeight.bold,
                                    color: zoho.isConnected ? AppTheme.accentColor : AppTheme.warningColor,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      Expanded(
                        child: Container(
                          padding: const EdgeInsets.all(14),
                          decoration: BoxDecoration(
                            color: isDark ? const Color(0xFF1E293B).withValues(alpha: 0.6) : const Color(0xFFF1F5F9),
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(
                              color: isDark ? const Color(0xFF334155) : const Color(0xFFE2E8F0),
                            ),
                          ),
                          child: zoho.isConnected
                              ? Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Row(
                                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                          children: [
                                            const Text('ORGANIZATION DETAILS', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, letterSpacing: 0.5, color: Colors.grey)),
                                            if (zoho.lastSyncAt != null && !isMobile)
                                              Container(
                                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                                decoration: BoxDecoration(
                                                  color: AppTheme.accentColor.withValues(alpha: 0.1),
                                                  borderRadius: BorderRadius.circular(6),
                                                ),
                                                child: Text(
                                                  'Synced: ${zoho.lastSyncAt!.toLocal().toString().split('.').first}',
                                                  style: const TextStyle(fontSize: 10.5, color: AppTheme.accentColor, fontWeight: FontWeight.w600),
                                                ),
                                              ),
                                          ],
                                        ),
                                        const SizedBox(height: 6),
                                        Text(
                                          zoho.organizationName ?? 'Primary Organization',
                                          maxLines: 1,
                                          overflow: TextOverflow.ellipsis,
                                          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold),
                                        ),
                                        const SizedBox(height: 2),
                                        Text(
                                          'Org ID: ${zoho.organizationId ?? "N/A"} • ${zoho.apiDomain ?? "https://books.zoho.in"}',
                                          maxLines: 1,
                                          overflow: TextOverflow.ellipsis,
                                          style: TextStyle(fontSize: 11, color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
                                        ),
                                      ],
                                    ),
                                    const SizedBox(height: 10),
                                    // Compact 3-Column Master Data Metrics
                                    Row(
                                      children: [
                                        Expanded(
                                          child: _buildMasterDataMetricTile(
                                            title: 'Accounts',
                                            count: zoho.accountsCount,
                                            icon: Icons.account_tree_outlined,
                                            color: AppTheme.primaryColor,
                                            onTap: () => _showChartOfAccountsDialog(context),
                                            isDark: isDark,
                                          ),
                                        ),
                                        const SizedBox(width: 8),
                                        Expanded(
                                          child: _buildMasterDataMetricTile(
                                            title: 'Taxes',
                                            count: zoho.taxesCount,
                                            icon: Icons.receipt_long_outlined,
                                            color: Colors.purple,
                                            onTap: () => _showTaxesDialog(context),
                                            isDark: isDark,
                                          ),
                                        ),
                                        const SizedBox(width: 8),
                                        Expanded(
                                          child: _buildMasterDataMetricTile(
                                            title: 'Vendors',
                                            count: zoho.vendorsCount,
                                            icon: Icons.people_outline_rounded,
                                            color: Colors.amber,
                                            onTap: () => _showVendorsDialog(context),
                                            isDark: isDark,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ],
                                )
                              : Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        const Text(
                                          'ZOHO ERP CONNECTION SETUP',
                                          style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, letterSpacing: 0.5, color: Colors.grey),
                                        ),
                                        const SizedBox(height: 10),
                                        Row(
                                          crossAxisAlignment: CrossAxisAlignment.start,
                                          children: [
                                            Icon(Icons.lock_outline_rounded, size: 18, color: AppTheme.primaryColor),
                                            const SizedBox(width: 8),
                                            Expanded(
                                              child: Text(
                                                'Connect your Zoho Books organization via official OAuth 2.0 to automate bill posting, vendor matching, and TDS export.',
                                                style: TextStyle(fontSize: 12, height: 1.4, color: isDark ? const Color(0xFFCBD5E1) : const Color(0xFF475569)),
                                              ),
                                            ),
                                          ],
                                        ),
                                      ],
                                    ),
                                    Container(
                                      padding: const EdgeInsets.all(8),
                                      decoration: BoxDecoration(
                                        color: isDark ? const Color(0xFF0F172A) : Colors.white,
                                        borderRadius: BorderRadius.circular(8),
                                        border: Border.all(color: isDark ? const Color(0xFF334155) : const Color(0xFFE2E8F0)),
                                      ),
                                      child: const Row(
                                        children: [
                                          Icon(Icons.verified_outlined, size: 15, color: AppTheme.accentColor),
                                          SizedBox(width: 8),
                                          Expanded(
                                            child: Text(
                                              'Supports Zoho India (.IN), US (.COM), EU (.EU), and AU (.COM.AU).',
                                              style: TextStyle(fontSize: 11, color: Colors.grey),
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                  ],
                                ),
                        ),
                      ),
                      const SizedBox(height: 16),
                      if (zoho.isConnected)
                        Row(
                          children: [
                            Expanded(
                              child: ElevatedButton.icon(
                                onPressed: intProvider.isSyncingZoho
                                    ? null
                                    : () async {
                                        await intProvider.syncZohoNow();
                                        if (context.mounted) {
                                          ScaffoldMessenger.of(context).showSnackBar(
                                            const SnackBar(
                                              content: Text('Zoho Books Master Data Synced Successfully!'),
                                              backgroundColor: AppTheme.accentColor,
                                            ),
                                          );
                                        }
                                      },
                                icon: intProvider.isSyncingZoho
                                    ? const SizedBox(
                                        width: 14,
                                        height: 14,
                                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                                      )
                                    : const Icon(Icons.sync_rounded, size: 16),
                                label: Text(intProvider.isSyncingZoho ? 'Syncing...' : 'Sync Master Data'),
                              ),
                            ),
                            const SizedBox(width: 10),
                            OutlinedButton.icon(
                              onPressed: () => intProvider.disconnectZoho(),
                              style: OutlinedButton.styleFrom(
                                foregroundColor: AppTheme.errorColor,
                                side: const BorderSide(color: AppTheme.errorColor),
                              ),
                              icon: const Icon(Icons.link_off_rounded, size: 16),
                              label: const Text('Disconnect Zoho'),
                            ),
                          ],
                        )
                      else
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton.icon(
                            onPressed: () => _startAutomaticZohoAuth(),
                            icon: const Icon(Icons.link_rounded, size: 16),
                            label: const Text('Connect Zoho Books'),
                          ),
                        ),
                    ],
                  ),
                );

                final imapCard = GlassCard(
                  padding: EdgeInsets.all(isMobile ? 16 : 22),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: Row(
                              children: [
                                Container(
                                  padding: const EdgeInsets.all(10),
                                  decoration: BoxDecoration(
                                    color: AppTheme.secondaryColor.withValues(alpha: 0.1),
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  child: const Icon(Icons.email_outlined, color: AppTheme.secondaryColor, size: 24),
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      const Text('IMAP Mailbox', style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold)),
                                      const SizedBox(height: 2),
                                      Text(
                                        isEmailConnected
                                            ? 'Connected as ${email.username ?? _imapUsernameController.text}'
                                            : 'Fetch incoming invoices automatically',
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: TextStyle(fontSize: 11.5, color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: (isEmailConnected ? AppTheme.accentColor : AppTheme.warningColor).withValues(alpha: 0.15),
                              borderRadius: BorderRadius.circular(20),
                              border: Border.all(
                                color: isEmailConnected ? AppTheme.accentColor : AppTheme.warningColor,
                                width: 1,
                              ),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(
                                  isEmailConnected ? Icons.check_circle_rounded : Icons.radio_button_unchecked_rounded,
                                  size: 13,
                                  color: isEmailConnected ? AppTheme.accentColor : AppTheme.warningColor,
                                ),
                                const SizedBox(width: 4),
                                Text(
                                  isEmailConnected ? 'Connected' : 'Disconnected',
                                  style: TextStyle(
                                    fontSize: 11,
                                    fontWeight: FontWeight.bold,
                                    color: isEmailConnected ? AppTheme.accentColor : AppTheme.warningColor,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      Expanded(
                        child: Container(
                          padding: const EdgeInsets.all(14),
                          decoration: BoxDecoration(
                            color: isDark ? const Color(0xFF1E293B).withValues(alpha: 0.6) : const Color(0xFFF1F5F9),
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(
                              color: isDark ? const Color(0xFF334155) : const Color(0xFFE2E8F0),
                            ),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  const Text('MAILBOX CREDENTIALS & SERVER', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, letterSpacing: 0.5, color: Colors.grey)),
                                  if (email.lastSyncTime != null && !isMobile)
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                      decoration: BoxDecoration(
                                        color: AppTheme.accentColor.withValues(alpha: 0.1),
                                        borderRadius: BorderRadius.circular(6),
                                      ),
                                      child: Text(
                                        'Synced: ${email.lastSyncTime!.toLocal().toString().split('.').first}',
                                        style: const TextStyle(fontSize: 10.5, color: AppTheme.accentColor, fontWeight: FontWeight.w600),
                                      ),
                                    )
                                  else if (isEmailConnected && !isMobile)
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                      decoration: BoxDecoration(
                                        color: AppTheme.accentColor.withValues(alpha: 0.1),
                                        borderRadius: BorderRadius.circular(6),
                                      ),
                                      child: const Text(
                                        'SSL Port 993 Active',
                                        style: TextStyle(fontSize: 10.5, color: AppTheme.accentColor, fontWeight: FontWeight.w600),
                                      ),
                                    ),
                                ],
                              ),
                              const SizedBox(height: 8),
                              // 2 Compact rows of inputs
                              Row(
                                children: [
                                  Expanded(
                                    flex: 3,
                                    child: TextFormField(
                                      controller: _imapServerController,
                                      style: const TextStyle(fontSize: 13),
                                      decoration: InputDecoration(
                                        labelText: 'IMAP Host / Server',
                                        isDense: true,
                                        contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
                                        filled: true,
                                        fillColor: isDark ? const Color(0xFF0F172A) : Colors.white,
                                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    flex: 1,
                                    child: TextFormField(
                                      controller: _imapPortController,
                                      keyboardType: TextInputType.number,
                                      style: const TextStyle(fontSize: 13),
                                      decoration: InputDecoration(
                                        labelText: 'Port (993)',
                                        isDense: true,
                                        contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
                                        filled: true,
                                        fillColor: isDark ? const Color(0xFF0F172A) : Colors.white,
                                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 8),
                              Row(
                                children: [
                                  Expanded(
                                    flex: 1,
                                    child: TextFormField(
                                      controller: _imapUsernameController,
                                      style: const TextStyle(fontSize: 13),
                                      decoration: InputDecoration(
                                        labelText: 'Account Username / Email',
                                        isDense: true,
                                        contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
                                        filled: true,
                                        fillColor: isDark ? const Color(0xFF0F172A) : Colors.white,
                                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    flex: 1,
                                    child: TextFormField(
                                      controller: _imapPasswordController,
                                      obscureText: _obscurePassword,
                                      style: const TextStyle(fontSize: 13),
                                      decoration: InputDecoration(
                                        labelText: 'Password / App Password',
                                        hintText: isEmailConnected ? '••••••••••••••••' : '16-char App Password',
                                        isDense: true,
                                        contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
                                        filled: true,
                                        fillColor: isDark ? const Color(0xFF0F172A) : Colors.white,
                                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                                        suffixIcon: IconButton(
                                          padding: EdgeInsets.zero,
                                          constraints: const BoxConstraints(),
                                          icon: Icon(
                                            _obscurePassword ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                                            size: 16,
                                            color: Colors.grey,
                                          ),
                                          onPressed: () {
                                            setState(() {
                                              _obscurePassword = !_obscurePassword;
                                            });
                                          },
                                        ),
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),
                      if (isEmailConnected)
                        Row(
                          children: [
                            Expanded(
                              child: ElevatedButton.icon(
                                onPressed: intProvider.isSyncingEmail
                                    ? null
                                    : () async {
                                        final scaffoldMessenger = ScaffoldMessenger.of(context);
                                        await intProvider.syncEmailNow();
                                        scaffoldMessenger.showSnackBar(
                                          SnackBar(
                                            content: Text(
                                              intProvider.errorMessage != null
                                                  ? 'Email sync error: ${intProvider.errorMessage}'
                                                  : 'Emails synced successfully! Checked for new invoice attachments.',
                                            ),
                                            backgroundColor: intProvider.errorMessage != null ? AppTheme.errorColor : AppTheme.accentColor,
                                          ),
                                        );
                                      },
                                icon: intProvider.isSyncingEmail
                                    ? const SizedBox(
                                        width: 14,
                                        height: 14,
                                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                                      )
                                    : const Icon(Icons.sync_rounded, size: 16),
                                label: Text(intProvider.isSyncingEmail ? 'Syncing...' : 'Sync Emails Now'),
                              ),
                            ),
                            const SizedBox(width: 8),
                            OutlinedButton.icon(
                              onPressed: intProvider.isLoading
                                  ? null
                                  : () async {
                                      final scaffoldMessenger = ScaffoldMessenger.of(context);
                                      final ok = await intProvider.saveEmailConfig(
                                        EmailConfig(
                                          imapServer: _imapServerController.text.trim(),
                                          imapPort: int.tryParse(_imapPortController.text) ?? 993,
                                          username: _imapUsernameController.text.trim(),
                                          password: _imapPasswordController.text,
                                        ),
                                      );
                                      scaffoldMessenger.showSnackBar(
                                        SnackBar(
                                          content: Text(
                                            ok
                                                ? 'Mailbox configuration updated and verified!'
                                                : 'Error: ${intProvider.errorMessage ?? "Failed to save settings"}',
                                          ),
                                          backgroundColor: ok ? AppTheme.accentColor : AppTheme.errorColor,
                                        ),
                                      );
                                    },
                              icon: const Icon(Icons.save_outlined, size: 16),
                              label: const Text('Update'),
                            ),
                            const SizedBox(width: 8),
                            OutlinedButton.icon(
                              onPressed: () async {
                                final scaffoldMessenger = ScaffoldMessenger.of(context);
                                await intProvider.disconnectEmail();
                                _imapPasswordController.clear();
                                scaffoldMessenger.showSnackBar(
                                  const SnackBar(
                                    content: Text('Email mailbox disconnected.'),
                                    backgroundColor: AppTheme.warningColor,
                                  ),
                                );
                              },
                              style: OutlinedButton.styleFrom(
                                foregroundColor: AppTheme.errorColor,
                                side: const BorderSide(color: AppTheme.errorColor),
                              ),
                              icon: const Icon(Icons.link_off_rounded, size: 16),
                              label: const Text('Disconnect'),
                            ),
                          ],
                        )
                      else
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton.icon(
                            onPressed: intProvider.isLoading
                                ? null
                                : () async {
                                    final scaffoldMessenger = ScaffoldMessenger.of(context);
                                    if (_imapUsernameController.text.trim().isEmpty || _imapPasswordController.text.isEmpty) {
                                      scaffoldMessenger.showSnackBar(
                                        const SnackBar(
                                          content: Text('Please enter both Email Address and App Password to connect.'),
                                          backgroundColor: AppTheme.warningColor,
                                        ),
                                      );
                                      return;
                                    }
                                    final ok = await intProvider.saveEmailConfig(
                                      EmailConfig(
                                        imapServer: _imapServerController.text.trim(),
                                        imapPort: int.tryParse(_imapPortController.text) ?? 993,
                                        username: _imapUsernameController.text.trim(),
                                        password: _imapPasswordController.text,
                                      ),
                                    );
                                    scaffoldMessenger.showSnackBar(
                                      SnackBar(
                                        content: Text(
                                          ok
                                              ? 'Email Connected Successfully! IMAP handshake verified.'
                                              : 'Connection failed: ${intProvider.errorMessage ?? "Please check App Password"}',
                                        ),
                                        backgroundColor: ok ? AppTheme.accentColor : AppTheme.errorColor,
                                      ),
                                    );
                                  },
                            icon: intProvider.isLoading
                                ? const SizedBox(
                                    width: 14,
                                    height: 14,
                                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                                  )
                                : const Icon(Icons.link_rounded, size: 16),
                            label: Text(intProvider.isLoading ? 'Connecting...' : 'Connect Mailbox'),
                          ),
                        ),
                    ],
                  ),
                );

                if (isWide) {
                  return IntrinsicHeight(
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Expanded(child: zohoCard),
                        const SizedBox(width: 24),
                        Expanded(child: imapCard),
                      ],
                    ),
                  );
                }

                return Column(
                  children: [
                    zohoCard,
                    const SizedBox(height: 20),
                    imapCard,
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}
