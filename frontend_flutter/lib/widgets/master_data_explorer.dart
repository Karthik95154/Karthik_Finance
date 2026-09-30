import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../config/theme.dart';
import '../models/integration_models.dart';
import '../providers/integration_provider.dart';
import 'glass_card.dart';

class MasterDataExplorerWidget extends StatefulWidget {
  const MasterDataExplorerWidget({super.key});

  @override
  State<MasterDataExplorerWidget> createState() => _MasterDataExplorerWidgetState();
}

class _MasterDataExplorerWidgetState extends State<MasterDataExplorerWidget> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final TextEditingController _searchController = TextEditingController();
  String _selectedAccountType = 'ALL';

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final intProv = Provider.of<IntegrationProvider>(context, listen: false);
      if (intProv.masterAccounts.isEmpty) {
        intProv.fetchZohoMasterData();
      }
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final intProv = Provider.of<IntegrationProvider>(context);
    final zohoStatus = intProv.zohoStatus;
    final accounts = intProv.masterAccounts;
    final taxes = intProv.masterTaxes;
    final vendors = intProv.masterVendors;
    final isLoading = intProv.isLoadingMasterData || intProv.isSyncingZoho;

    final query = _searchController.text.toLowerCase().trim();

    final filteredAccounts = accounts.where((a) {
      if (_selectedAccountType != 'ALL') {
        final aType = (a.type ?? '').toUpperCase();
        if (!aType.contains(_selectedAccountType)) return false;
      }
      if (query.isNotEmpty) {
        final name = a.name.toLowerCase();
        final code = (a.code ?? '').toLowerCase();
        final type = (a.type ?? '').toLowerCase();
        if (!name.contains(query) && !code.contains(query) && !type.contains(query)) {
          return false;
        }
      }
      return true;
    }).toList();

    final filteredTaxes = taxes.where((t) {
      if (query.isNotEmpty) {
        final name = t.name.toLowerCase();
        final type = (t.type ?? '').toLowerCase();
        final pct = t.percentage.toString();
        if (!name.contains(query) && !type.contains(query) && !pct.contains(query)) {
          return false;
        }
      }
      return true;
    }).toList();

    final filteredVendors = vendors.where((v) {
      if (query.isNotEmpty) {
        final name = v.name.toLowerCase();
        final gstin = (v.gstin ?? '').toLowerCase();
        final pan = (v.pan ?? '').toLowerCase();
        if (!name.contains(query) && !gstin.contains(query) && !pan.contains(query)) {
          return false;
        }
      }
      return true;
    }).toList();

    return GlassCard(
      padding: const EdgeInsets.all(24),
      borderRadius: 20,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header Bar
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  gradient: AppTheme.primaryGradient,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.account_tree_rounded, color: Colors.white, size: 22),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Zoho Books Master Data Directory',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, letterSpacing: -0.3),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'Authoritative Chart of Accounts (COA), statutory GST tax rates, and contact entities cached in database',
                      style: TextStyle(
                        fontSize: 12,
                        color: isDark ? AppTheme.darkTextMuted : const Color(0xFF64748B),
                      ),
                    ),
                  ],
                ),
              ),
              ElevatedButton.icon(
                onPressed: isLoading
                    ? null
                    : () async {
                        final sm = ScaffoldMessenger.of(context);
                        await intProv.syncZohoNow();
                        if (mounted) {
                          sm.showSnackBar(
                            const SnackBar(
                              content: Text('Zoho master data successfully synchronized!'),
                              backgroundColor: AppTheme.accentColor,
                            ),
                          );
                        }
                      },
                icon: isLoading
                    ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Icon(Icons.sync_rounded, size: 16),
                label: const Text('Sync Master Data'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primaryColor,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),

          // Search & Tab Bar
          Row(
            children: [
              Expanded(
                child: TabBar(
                  controller: _tabController,
                  isScrollable: true,
                  tabAlignment: TabAlignment.start,
                  tabs: [
                    Tab(
                      child: Row(
                        children: [
                          const Icon(Icons.dashboard_rounded, size: 16),
                          const SizedBox(width: 6),
                          const Text('Overview'),
                        ],
                      ),
                    ),
                    Tab(
                      child: Row(
                        children: [
                          const Icon(Icons.menu_book_rounded, size: 16),
                          const SizedBox(width: 6),
                          Text('Chart of Accounts (${accounts.length})'),
                        ],
                      ),
                    ),
                    Tab(
                      child: Row(
                        children: [
                          const Icon(Icons.percent_rounded, size: 16),
                          const SizedBox(width: 6),
                          Text('GST & Taxes (${taxes.length})'),
                        ],
                      ),
                    ),
                    Tab(
                      child: Row(
                        children: [
                          const Icon(Icons.people_alt_rounded, size: 16),
                          const SizedBox(width: 6),
                          Text('Vendors (${vendors.length})'),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 16),
              SizedBox(
                width: 240,
                child: TextField(
                  controller: _searchController,
                  onChanged: (_) => setState(() {}),
                  decoration: InputDecoration(
                    hintText: 'Search master data...',
                    prefixIcon: const Icon(Icons.search_rounded, size: 18),
                    isDense: true,
                    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                    suffixIcon: _searchController.text.isNotEmpty
                        ? IconButton(
                            icon: const Icon(Icons.clear, size: 16),
                            onPressed: () {
                              _searchController.clear();
                              setState(() {});
                            },
                          )
                        : null,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Tab Content
          SizedBox(
            height: 380,
            child: TabBarView(
              controller: _tabController,
              children: [
                // 1. Overview Tab
                _buildOverviewTab(zohoStatus, accounts.length, taxes.length, vendors.length, isDark),

                // 2. Chart of Accounts Tab
                _buildAccountsTab(filteredAccounts, isDark),

                // 3. Taxes Tab
                _buildTaxesTab(filteredTaxes, isDark),

                // 4. Vendors Tab
                _buildVendorsTab(filteredVendors, isDark),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildOverviewTab(
    ZohoConnectionStatus status,
    int accCount,
    int taxCount,
    int venCount,
    bool isDark,
  ) {
    final dateFormat = DateFormat('dd MMM yyyy, hh:mm a');

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: _buildMetricPill(
                  Icons.menu_book_rounded,
                  'Chart of Accounts',
                  '$accCount Accounts',
                  'Synced with Zoho General Ledger',
                  AppTheme.primaryColor,
                  isDark,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: _buildMetricPill(
                  Icons.percent_rounded,
                  'Tax Rates & Rules',
                  '$taxCount Tax Codes',
                  'HSN/SAC & statutory tax percentages',
                  const Color(0xFF10B981),
                  isDark,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: _buildMetricPill(
                  Icons.people_alt_rounded,
                  'Vendor Directory',
                  '$venCount Vendors',
                  'Registered contacts & GSTIN profiles',
                  const Color(0xFF8B5CF6),
                  isDark,
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: isDark ? const Color(0xFF0F172A).withValues(alpha: 0.5) : const Color(0xFFF8FAFC),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Synchronization Metadata', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                const SizedBox(height: 12),
                _buildMetaRow('Active Zoho Organization:', status.organizationName ?? 'Not Connected', isDark),
                const SizedBox(height: 8),
                _buildMetaRow('Zoho Organization ID:', status.organizationId ?? '—', isDark),
                const SizedBox(height: 8),
                _buildMetaRow('Last Master Data Sync:', status.lastSyncAt != null ? dateFormat.format(status.lastSyncAt!) : 'Never', isDark),
                const SizedBox(height: 8),
                _buildMetaRow('API Domain / Region:', status.apiDomain ?? 'https://accounts.zoho.in', isDark),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAccountsTab(List<ZohoMasterAccount> accounts, bool isDark) {
    const types = ['ALL', 'EXPENSE', 'ASSET', 'LIABILITY', 'EQUITY', 'INCOME'];

    return Column(
      children: [
        // Filter Chips
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: types.map((t) {
              final isSelected = _selectedAccountType == t;
              return Padding(
                padding: const EdgeInsets.only(right: 8),
                child: ChoiceChip(
                  label: Text(t),
                  selected: isSelected,
                  onSelected: (val) {
                    if (val) setState(() => _selectedAccountType = t);
                  },
                  labelStyle: TextStyle(
                    fontSize: 11,
                    fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                    color: isSelected ? Colors.white : (isDark ? AppTheme.darkTextMuted : const Color(0xFF64748B)),
                  ),
                ),
              );
            }).toList(),
          ),
        ),
        const SizedBox(height: 12),

        // Accounts Table
        Expanded(
          child: accounts.isEmpty
              ? const Center(child: Text('No Chart of Accounts found matching filters.'))
              : ListView.separated(
                  itemCount: accounts.length,
                  separatorBuilder: (_, index) => const Divider(height: 1),
                  itemBuilder: (context, index) {
                    final acc = accounts[index];
                    return ListTile(
                      dense: true,
                      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
                      title: Row(
                        children: [
                          Expanded(
                            child: Text(
                              acc.name,
                              style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                            ),
                          ),
                          if (acc.code != null && acc.code!.isNotEmpty)
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: AppTheme.primaryColor.withValues(alpha: 0.12),
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: Text(
                                acc.code!,
                                style: const TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.bold,
                                  color: AppTheme.primaryColor,
                                ),
                              ),
                            ),
                        ],
                      ),
                      subtitle: Text(
                        'Type: ${acc.type ?? "Expense"} • ID: ${acc.zohoAccountId ?? acc.id}',
                        style: TextStyle(
                          fontSize: 11,
                          color: isDark ? AppTheme.darkTextMuted : const Color(0xFF64748B),
                        ),
                      ),
                      leading: Icon(
                        (acc.type ?? '').toLowerCase().contains('expense')
                            ? Icons.trending_down_rounded
                            : ((acc.type ?? '').toLowerCase().contains('income')
                                ? Icons.trending_up_rounded
                                : Icons.account_balance_rounded),
                        size: 18,
                        color: AppTheme.primaryLight,
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }

  Widget _buildTaxesTab(List<ZohoMasterTax> taxes, bool isDark) {
    if (taxes.isEmpty) {
      return const Center(child: Text('No GST Tax rates found.'));
    }

    return ListView.separated(
      itemCount: taxes.length,
      separatorBuilder: (_, index) => const Divider(height: 1),
      itemBuilder: (context, index) {
        final tax = taxes[index];
        return ListTile(
          dense: true,
          contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
          leading: Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: const Color(0xFF10B981).withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Icon(Icons.percent_rounded, size: 16, color: Color(0xFF10B981)),
          ),
          title: Text(tax.name, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
          subtitle: Text(
            'Type: ${tax.type ?? "GST"} • ID: ${tax.zohoTaxId ?? tax.id}',
            style: TextStyle(
              fontSize: 11,
              color: isDark ? AppTheme.darkTextMuted : const Color(0xFF64748B),
            ),
          ),
          trailing: Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: const Color(0xFF10B981).withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              '${tax.percentage.toStringAsFixed(1)}%',
              style: const TextStyle(
                fontWeight: FontWeight.w800,
                color: Color(0xFF10B981),
                fontSize: 12,
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildVendorsTab(List<ZohoMasterVendor> vendors, bool isDark) {
    if (vendors.isEmpty) {
      return const Center(child: Text('No Vendors found.'));
    }

    return ListView.separated(
      itemCount: vendors.length,
      separatorBuilder: (_, index) => const Divider(height: 1),
      itemBuilder: (context, index) {
        final ven = vendors[index];
        return ListTile(
          dense: true,
          contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
          leading: Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: const Color(0xFF8B5CF6).withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Icon(Icons.business_rounded, size: 16, color: Color(0xFF8B5CF6)),
          ),
          title: Text(ven.name, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
          subtitle: Text(
            'GSTIN: ${ven.gstin ?? "Unregistered"} • PAN: ${ven.pan ?? "—"}',
            style: TextStyle(
              fontSize: 11,
              color: isDark ? AppTheme.darkTextMuted : const Color(0xFF64748B),
            ),
          ),
          trailing: Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              color: AppTheme.accentColor.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(6),
            ),
            child: const Text(
              'Synced',
              style: TextStyle(
                fontSize: 10.5,
                fontWeight: FontWeight.bold,
                color: AppTheme.accentColor,
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildMetricPill(
    IconData icon,
    String title,
    String count,
    String sub,
    Color color,
    bool isDark,
  ) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withValues(alpha: isDark ? 0.12 : 0.06),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.25)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 18, color: color),
              const SizedBox(width: 8),
              Text(title, style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: color)),
            ],
          ),
          const SizedBox(height: 10),
          Text(count, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
          const SizedBox(height: 4),
          Text(
            sub,
            style: TextStyle(
              fontSize: 11,
              color: isDark ? AppTheme.darkTextMuted : const Color(0xFF64748B),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMetaRow(String label, String value, bool isDark) {
    return Row(
      children: [
        Text(
          label,
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: isDark ? AppTheme.darkTextMuted : const Color(0xFF64748B),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            value,
            style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.bold),
          ),
        ),
      ],
    );
  }
}
