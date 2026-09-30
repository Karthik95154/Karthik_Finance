import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/theme.dart';
import '../../providers/auth_provider.dart';
import '../../providers/theme_provider.dart';
import '../../widgets/aurora_background.dart';
import '../../widgets/glass_card.dart';
import '../../widgets/app_shell.dart';
import '../auth/login_screen.dart';
import '../auth/signup_screen.dart';

class LandingScreen extends StatefulWidget {
  const LandingScreen({super.key});

  @override
  State<LandingScreen> createState() => _LandingScreenState();
}

class _LandingScreenState extends State<LandingScreen> {
  final ScrollController _scrollController = ScrollController();
  final GlobalKey _featuresKey = GlobalKey();
  final GlobalKey _workflowKey = GlobalKey();
  final GlobalKey _complianceKey = GlobalKey();

  void _scrollToSection(GlobalKey key) {
    final context = key.currentContext;
    if (context != null) {
      Scrollable.ensureVisible(
        context,
        duration: const Duration(milliseconds: 600),
        curve: Curves.easeInOutCubic,
      );
    }
  }

  void _navigateToAuth(BuildContext context, {bool isSignup = false}) {
    final auth = Provider.of<AuthProvider>(context, listen: false);
    if (auth.isAuthenticated) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const AppShell()),
      );
    } else {
      Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => isSignup ? const SignUpScreen() : const LoginScreen()),
      );
    }
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final themeProv = Provider.of<ThemeProvider>(context);
    final authProv = Provider.of<AuthProvider>(context);
    final size = MediaQuery.of(context).size;
    final isDesktop = size.width >= 1024;
    final isTablet = size.width >= 768 && size.width < 1024;

    return Scaffold(
      body: AuroraBackground(
        child: Column(
          children: [
            // Top Navigation Bar
            _buildNavbar(context, isDark, themeProv, authProv, isDesktop),

            // Scrollable Landing Page Content
            Expanded(
              child: SingleChildScrollView(
                controller: _scrollController,
                physics: const BouncingScrollPhysics(),
                child: Column(
                  children: [
                    // Hero Section
                    _buildHeroSection(context, isDark, isDesktop, isTablet),

                    // Metrics & Statutory Badges Bar
                    _buildMetricsBar(context, isDark, isDesktop),

                    // Core Capabilities Grid
                    _buildCapabilitiesSection(context, isDark, isDesktop),

                    // Interactive Mathematical Pipeline Showcase
                    _buildPipelineSection(context, isDark, isDesktop),

                    // Live Verification Preview Card
                    _buildLivePreviewSection(context, isDark, isDesktop),

                    // Call To Action Banner
                    _buildCtaBanner(context, isDark, isDesktop),

                    // Footer
                    _buildFooter(context, isDark, isDesktop),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildNavbar(
    BuildContext context,
    bool isDark,
    ThemeProvider themeProv,
    AuthProvider authProv,
    bool isDesktop,
  ) {
    return Container(
      height: 72,
      padding: EdgeInsets.symmetric(horizontal: isDesktop ? 48 : 20),
      decoration: BoxDecoration(
        color: isDark
            ? const Color(0xFF070B14).withValues(alpha: 0.85)
            : Colors.white.withValues(alpha: 0.85),
        border: Border(
          bottom: BorderSide(
            color: isDark
                ? Colors.white.withValues(alpha: 0.08)
                : Colors.black.withValues(alpha: 0.06),
          ),
        ),
      ),
      child: Row(
        children: [
          // Logo & Brand
          InkWell(
            onTap: () => _scrollController.animateTo(0, duration: const Duration(milliseconds: 500), curve: Curves.easeOut),
            borderRadius: BorderRadius.circular(10),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  padding: const EdgeInsets.all(7),
                  decoration: BoxDecoration(
                    gradient: AppTheme.primaryGradient,
                    borderRadius: BorderRadius.circular(10),
                    boxShadow: [
                      BoxShadow(
                        color: AppTheme.primaryColor.withValues(alpha: 0.35),
                        blurRadius: 10,
                        offset: const Offset(0, 3),
                      ),
                    ],
                  ),
                  child: const Icon(Icons.account_balance_wallet_rounded, color: Colors.white, size: 18),
                ),
                const SizedBox(width: 8),
                Text(
                  'Sakshi Finance',
                  style: TextStyle(
                    fontSize: isDesktop ? 18 : 16,
                    fontWeight: FontWeight.w800,
                    letterSpacing: -0.5,
                    color: isDark ? Colors.white : const Color(0xFF0F172A),
                  ),
                ),
                if (isDesktop) ...[
                  const SizedBox(width: 6),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: AppTheme.primaryColor.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: AppTheme.primaryColor.withValues(alpha: 0.3)),
                    ),
                    child: const Text(
                      'ENTERPRISE',
                      style: TextStyle(
                        fontSize: 9,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 0.6,
                        color: AppTheme.primaryLight,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),

          const Spacer(),

          // Desktop Nav Links
          if (isDesktop) ...[
            _buildNavLink('Capabilities', () => _scrollToSection(_featuresKey), isDark),
            const SizedBox(width: 20),
            _buildNavLink('Workflow', () => _scrollToSection(_workflowKey), isDark),
            const SizedBox(width: 20),
            _buildNavLink('Statutory Compliance', () => _scrollToSection(_complianceKey), isDark),
            const SizedBox(width: 28),
          ],

          // Theme Toggle
          IconButton(
            icon: Icon(
              themeProv.isDarkMode ? Icons.light_mode_rounded : Icons.dark_mode_rounded,
              size: 20,
              color: isDark ? Colors.amber.shade300 : const Color(0xFF475569),
            ),
            tooltip: themeProv.isDarkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode',
            onPressed: () => themeProv.toggleTheme(),
          ),
          const SizedBox(width: 12),

          // Sign In / Workspace Action Buttons
          if (authProv.isAuthenticated)
            ElevatedButton.icon(
              onPressed: () => Navigator.of(context).pushReplacement(
                MaterialPageRoute(builder: (_) => const AppShell()),
              ),
              icon: const Icon(Icons.dashboard_rounded, size: 16),
              label: const Text('Go to Workspace', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryColor,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                elevation: 0,
              ),
            )
          else ...[
            TextButton(
              onPressed: () => _navigateToAuth(context, isSignup: false),
              style: TextButton.styleFrom(
                foregroundColor: isDark ? Colors.white70 : const Color(0xFF334155),
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              ),
              child: const Text('Sign In', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13.5)),
            ),
            const SizedBox(width: 10),
            ElevatedButton(
              onPressed: () => _navigateToAuth(context, isSignup: false),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryColor,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                elevation: 0,
                shadowColor: AppTheme.primaryColor.withValues(alpha: 0.4),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('Launch App', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5)),
                  SizedBox(width: 6),
                  Icon(Icons.arrow_forward_rounded, size: 15),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildNavLink(String title, VoidCallback onTap, bool isDark) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        child: Text(
          title,
          style: TextStyle(
            fontSize: 13.5,
            fontWeight: FontWeight.w600,
            color: isDark ? Colors.grey.shade300 : const Color(0xFF475569),
          ),
        ),
      ),
    );
  }

  Widget _buildHeroSection(BuildContext context, bool isDark, bool isDesktop, bool isTablet) {
    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: isDesktop ? 64 : 24,
        vertical: isDesktop ? 70 : 40,
      ),
      constraints: const BoxConstraints(maxWidth: 1200),
      child: Column(
        children: [
          // Sparkle AI Pill
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
            decoration: BoxDecoration(
              color: AppTheme.primaryColor.withValues(alpha: isDark ? 0.18 : 0.08),
              borderRadius: BorderRadius.circular(30),
              border: Border.all(color: AppTheme.primaryColor.withValues(alpha: 0.35)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.auto_awesome_rounded, size: 14, color: AppTheme.primaryLight),
                const SizedBox(width: 8),
                Text(
                  'AUTONOMOUS INVOICE PROCESSING & DOUBLE-ENTRY ENGINE',
                  style: TextStyle(
                    fontSize: isDesktop ? 11.5 : 10,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0.6,
                    color: isDark ? AppTheme.primaryLight : AppTheme.primaryDark,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          // Main Headline
          Text(
            'Autonomous Accounting,\nDeterministic Tax & Audit Integrity',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: isDesktop ? 46 : (isTablet ? 36 : 28),
              fontWeight: FontWeight.w900,
              letterSpacing: -1.2,
              height: 1.15,
              color: isDark ? Colors.white : const Color(0xFF0F172A),
            ),
          ),
          const SizedBox(height: 20),

          // Subtitle
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 780),
            child: Text(
              'Process complex multi-page vendor invoices with zero data loss. Automate Indian statutory tax compliance—TDS u/s 194C/J, Section 17(5) ITC validation, RCM Sec 9(3), and double-entry Zoho Books synchronization.',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: isDesktop ? 16 : 14,
                height: 1.6,
                fontWeight: FontWeight.w400,
                color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B),
              ),
            ),
          ),
          const SizedBox(height: 36),

          // CTA Buttons
          Wrap(
            spacing: 16,
            runSpacing: 12,
            alignment: WrapAlignment.center,
            children: [
              ElevatedButton(
                onPressed: () => _navigateToAuth(context, isSignup: false),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primaryColor,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 16),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  elevation: 6,
                  shadowColor: AppTheme.primaryColor.withValues(alpha: 0.5),
                ),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text('Access Workspace', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                    SizedBox(width: 8),
                    Icon(Icons.arrow_forward_rounded, size: 18),
                  ],
                ),
              ),
              OutlinedButton.icon(
                onPressed: () => _scrollToSection(_featuresKey),
                icon: const Icon(Icons.explore_outlined, size: 18),
                label: const Text('Explore Engine', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                style: OutlinedButton.styleFrom(
                  foregroundColor: isDark ? Colors.white : const Color(0xFF0F172A),
                  side: BorderSide(
                    color: isDark ? Colors.white.withValues(alpha: 0.2) : Colors.black.withValues(alpha: 0.15),
                    width: 1.5,
                  ),
                  padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildMetricsBar(BuildContext context, bool isDark, bool isDesktop) {
    final metrics = [
      {'val': '100%', 'lbl': 'Deterministic Balance', 'desc': 'Debits == Credits'},
      {'val': '0% Loss', 'lbl': 'Vision Extraction', 'desc': 'Line Items & HSN'},
      {'val': 'Sec 194C/J', 'lbl': 'Automated TDS', 'desc': 'Threshold & YTD'},
      {'val': 'Zoho Ready', 'lbl': 'API Synchronized', 'desc': '1-Click Post'},
    ];

    return Container(
      key: _complianceKey,
      margin: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      constraints: const BoxConstraints(maxWidth: 1100),
      child: GlassCard(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
        borderRadius: 16,
        child: isDesktop
            ? Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: metrics.map((m) => _buildMetricItem(m, isDark)).toList(),
              )
            : Wrap(
                spacing: 24,
                runSpacing: 20,
                alignment: WrapAlignment.spaceAround,
                children: metrics.map((m) => _buildMetricItem(m, isDark)).toList(),
              ),
      ),
    );
  }

  Widget _buildMetricItem(Map<String, String> m, bool isDark) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          m['val']!,
          style: const TextStyle(
            fontSize: 22,
            fontWeight: FontWeight.w900,
            color: AppTheme.primaryLight,
            letterSpacing: -0.5,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          m['lbl']!,
          style: TextStyle(
            fontSize: 12.5,
            fontWeight: FontWeight.bold,
            color: isDark ? Colors.white : const Color(0xFF0F172A),
          ),
        ),
        Text(
          m['desc']!,
          style: TextStyle(
            fontSize: 11,
            color: isDark ? Colors.grey.shade400 : Colors.grey.shade600,
          ),
        ),
      ],
    );
  }

  Widget _buildCapabilitiesSection(BuildContext context, bool isDark, bool isDesktop) {
    final capabilities = [
      {
        'icon': Icons.document_scanner_rounded,
        'title': 'VLM Invoice Extraction',
        'desc': 'Zero-loss extraction of vendor metadata, line items, quantities, HSN codes, and tax rates from PDF/Image invoices.',
        'tag': 'Vision AI',
        'color': const Color(0xFF0284C7),
      },
      {
        'icon': Icons.account_tree_outlined,
        'title': 'COA Classification',
        'desc': 'Contextual Chart of Accounts mapping with confidence scoring and full audit trail for all expense heads.',
        'tag': 'Intelligent Ledger',
        'color': const Color(0xFF6366F1),
      },
      {
        'icon': Icons.verified_user_outlined,
        'title': 'GST & ITC Engine',
        'desc': 'Deterministic Place of Supply resolution (Intra-state vs Inter-state) and Section 17(5) blocked credit rules.',
        'tag': 'Statutory Tax',
        'color': const Color(0xFF10B981),
      },
      {
        'icon': Icons.gavel_rounded,
        'title': 'TDS Withholding Engine',
        'desc': 'Automated Section 194C (Contractors) & 194J (Professional fees) assessment with YTD threshold monitoring.',
        'tag': 'Direct Tax',
        'color': const Color(0xFFF59E0B),
      },
      {
        'icon': Icons.calculate_outlined,
        'title': 'Mathematical Reconciliation',
        'desc': 'Multi-point verification validating line item totals, tax calculations, discounts, and vendor payable amounts.',
        'tag': 'Zero Discrepancy',
        'color': const Color(0xFF8B5CF6),
      },
      {
        'icon': Icons.sync_alt_rounded,
        'title': 'Zoho Books Integration',
        'desc': '1-click export creating balanced journal entries and vendor bills with direct audit log provenance.',
        'tag': 'ERP Sync',
        'color': const Color(0xFFEC4899),
      },
    ];

    return Container(
      key: _featuresKey,
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 50),
      constraints: const BoxConstraints(maxWidth: 1200),
      child: Column(
        children: [
          // Section Title
          Text(
            'Institutional Financial Capabilities',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: isDesktop ? 32 : 24,
              fontWeight: FontWeight.w800,
              letterSpacing: -0.8,
              color: isDark ? Colors.white : const Color(0xFF0F172A),
            ),
          ),
          const SizedBox(height: 10),
          Text(
            'Engineered for chartered accountants, CFOs, and finance teams requiring precision.',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 14.5,
              color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B),
            ),
          ),
          const SizedBox(height: 40),

          // Grid
          LayoutBuilder(
            builder: (context, constraints) {
              final crossAxisCount = constraints.maxWidth > 900 ? 3 : (constraints.maxWidth > 600 ? 2 : 1);
              return Wrap(
                spacing: 20,
                runSpacing: 20,
                children: capabilities.map((item) {
                  final width = (constraints.maxWidth - (crossAxisCount - 1) * 20) / crossAxisCount;
                  return SizedBox(
                    width: width,
                    child: _buildCapabilityCard(item, isDark),
                  );
                }).toList(),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildCapabilityCard(Map<String, dynamic> item, bool isDark) {
    final color = item['color'] as Color;
    return GlassCard(
      padding: const EdgeInsets.all(22),
      borderRadius: 16,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: isDark ? 0.2 : 0.1),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: color.withValues(alpha: 0.3)),
                ),
                child: Icon(item['icon'] as IconData, color: color, size: 22),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  item['tag'] as String,
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                    color: color,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),
          Text(
            item['title'] as String,
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: isDark ? Colors.white : const Color(0xFF0F172A),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            item['desc'] as String,
            style: TextStyle(
              fontSize: 12.5,
              height: 1.5,
              color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPipelineSection(BuildContext context, bool isDark, bool isDesktop) {
    final steps = [
      {'step': '01', 'title': 'Ingestion', 'desc': 'PDF/Image OCR with SHA-256 deduplication'},
      {'step': '02', 'title': 'VLM Extraction', 'desc': 'Vendor, Line Items, HSN & Tax Heads'},
      {'step': '03', 'title': 'Statutory Tax', 'desc': 'TDS u/s 194C/J & Section 17(5) ITC'},
      {'step': '04', 'title': 'Double-Entry', 'desc': 'Balanced Debit == Credit Ledger Generation'},
      {'step': '05', 'title': 'Zoho Export', 'desc': 'Direct ERP Journal & Bill Synchronization'},
    ];

    return Container(
      key: _workflowKey,
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 50),
      constraints: const BoxConstraints(maxWidth: 1200),
      child: Column(
        children: [
          Text(
            'The End-to-End Accounting Pipeline',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: isDesktop ? 30 : 22,
              fontWeight: FontWeight.w800,
              letterSpacing: -0.6,
              color: isDark ? Colors.white : const Color(0xFF0F172A),
            ),
          ),
          const SizedBox(height: 10),
          Text(
            'From raw invoice ingestion to ledger synchronization in seconds.',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 14,
              color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B),
            ),
          ),
          const SizedBox(height: 36),

          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: steps.map((s) {
                final isLast = s == steps.last;
                return Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 180,
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: isDark ? const Color(0xFF0F172A).withValues(alpha: 0.7) : Colors.white,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: isDark ? Colors.white.withValues(alpha: 0.1) : Colors.black.withValues(alpha: 0.08),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            s['step']!,
                            style: const TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.w900,
                              color: AppTheme.primaryLight,
                            ),
                          ),
                          const SizedBox(height: 6),
                          Text(
                            s['title']!,
                            style: TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.bold,
                              color: isDark ? Colors.white : const Color(0xFF0F172A),
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            s['desc']!,
                            style: TextStyle(
                              fontSize: 10.5,
                              height: 1.4,
                              color: isDark ? Colors.grey.shade400 : Colors.grey.shade600,
                            ),
                          ),
                        ],
                      ),
                    ),
                    if (!isLast)
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 10),
                        child: Icon(
                          Icons.arrow_forward_rounded,
                          size: 16,
                          color: isDark ? Colors.grey.shade600 : Colors.grey.shade400,
                        ),
                      ),
                  ],
                );
              }).toList(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLivePreviewSection(BuildContext context, bool isDark, bool isDesktop) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 40),
      constraints: const BoxConstraints(maxWidth: 1000),
      child: GlassCard(
        padding: const EdgeInsets.all(28),
        borderRadius: 20,
        enableGlow: true,
        glowColor: AppTheme.primaryLight,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    Container(
                      width: 10,
                      height: 10,
                      decoration: const BoxDecoration(
                        color: Color(0xFF10B981),
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'Live Settlement Engine Preview',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.bold,
                        color: isDark ? Colors.white : const Color(0xFF0F172A),
                      ),
                    ),
                  ],
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: const Color(0xFF10B981).withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: const Text(
                    '100% BALANCED',
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w800,
                      color: Color(0xFF10B981),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),

            // Visual Pipeline Strip
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: isDark ? Colors.black.withValues(alpha: 0.3) : const Color(0xFFF8FAFC),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                  color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06),
                ),
              ),
              child: SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: [
                    _buildPreviewPill('Base Subtotal', '₹1,00,000.00', const Color(0xFF0284C7), isDark),
                    const Padding(padding: EdgeInsets.symmetric(horizontal: 6), child: Text('➕', style: TextStyle(fontSize: 11))),
                    _buildPreviewPill('CGST (9%)', '₹9,000.00', const Color(0xFF6366F1), isDark),
                    const Padding(padding: EdgeInsets.symmetric(horizontal: 6), child: Text('➕', style: TextStyle(fontSize: 11))),
                    _buildPreviewPill('SGST (9%)', '₹9,000.00', const Color(0xFF6366F1), isDark),
                    const Padding(padding: EdgeInsets.symmetric(horizontal: 6), child: Text('🟰', style: TextStyle(fontSize: 11))),
                    _buildPreviewPill('Grand Total', '₹1,18,000.00', const Color(0xFF0F172A), isDark, isBold: true),
                    const Padding(padding: EdgeInsets.symmetric(horizontal: 6), child: Text('➖', style: TextStyle(fontSize: 11))),
                    _buildPreviewPill('TDS u/s 194C (2%)', '₹2,000.00', const Color(0xFFD97706), isDark),
                    const Padding(padding: EdgeInsets.symmetric(horizontal: 6), child: Text('➔', style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold))),
                    _buildPreviewPill('Net Payable', '₹1,16,000.00', const Color(0xFF10B981), isDark, isBold: true, isHighlight: true),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPreviewPill(String label, String val, Color color, bool isDark, {bool isBold = false, bool isHighlight = false}) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: isHighlight
            ? color.withValues(alpha: isDark ? 0.25 : 0.12)
            : (isDark ? Colors.white.withValues(alpha: 0.04) : Colors.white),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(
          color: isHighlight ? color.withValues(alpha: 0.8) : color.withValues(alpha: 0.25),
          width: isHighlight ? 1.5 : 1.0,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label.toUpperCase(),
            style: TextStyle(
              fontSize: 8.5,
              fontWeight: FontWeight.w700,
              color: isDark ? Colors.grey.shade400 : Colors.grey.shade600,
            ),
          ),
          Text(
            val,
            style: TextStyle(
              fontSize: 11.5,
              fontWeight: isBold || isHighlight ? FontWeight.w800 : FontWeight.w600,
              color: isHighlight ? (isDark ? Colors.white : color) : (isDark ? Colors.white : const Color(0xFF0F172A)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCtaBanner(BuildContext context, bool isDark, bool isDesktop) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 24, vertical: 40),
      padding: EdgeInsets.symmetric(horizontal: isDesktop ? 60 : 28, vertical: isDesktop ? 50 : 36),
      constraints: const BoxConstraints(maxWidth: 1100),
      decoration: BoxDecoration(
        gradient: AppTheme.primaryGradient,
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: AppTheme.primaryColor.withValues(alpha: 0.4),
            blurRadius: 30,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        children: [
          const Text(
            'Ready to Modernize Your Financial Accounting?',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.w900,
              color: Colors.white,
              letterSpacing: -0.6,
            ),
          ),
          const SizedBox(height: 12),
          const Text(
            'Experience zero-error autonomous tax extraction and seamless Zoho synchronization.',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 15,
              color: Colors.white70,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 28),
          ElevatedButton(
            onPressed: () => _navigateToAuth(context, isSignup: false),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.white,
              foregroundColor: AppTheme.primaryDark,
              padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              elevation: 4,
            ),
            child: const Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('Launch Workspace Now', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 15)),
                SizedBox(width: 8),
                Icon(Icons.arrow_forward_rounded, size: 18),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFooter(BuildContext context, bool isDark, bool isDesktop) {
    return Container(
      padding: EdgeInsets.symmetric(horizontal: isDesktop ? 48 : 24, vertical: 24),
      decoration: BoxDecoration(
        border: Border(
          top: BorderSide(
            color: isDark ? Colors.white.withValues(alpha: 0.08) : Colors.black.withValues(alpha: 0.06),
          ),
        ),
      ),
      child: isDesktop
          ? Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  '© 2026 Sakshi Finance Engine. All rights reserved.',
                  style: TextStyle(
                    fontSize: 12,
                    color: isDark ? Colors.grey.shade500 : Colors.grey.shade500,
                  ),
                ),
                Text(
                  'Institutional Financial Compliance',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: isDark ? Colors.grey.shade400 : Colors.grey.shade600,
                  ),
                ),
              ],
            )
          : Column(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Text(
                  '© 2026 Sakshi Finance Engine. All rights reserved.',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 12,
                    color: isDark ? Colors.grey.shade500 : Colors.grey.shade500,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  'Institutional Financial Compliance',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: isDark ? Colors.grey.shade400 : Colors.grey.shade600,
                  ),
                ),
              ],
            ),
    );
  }
}
