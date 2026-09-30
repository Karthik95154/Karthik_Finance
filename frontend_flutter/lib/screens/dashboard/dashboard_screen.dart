import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../../config/theme.dart';
import '../../models/invoice_models.dart';
import '../../providers/invoice_provider.dart';
import '../../widgets/glass_card.dart';
import '../../widgets/metric_card.dart';
import '../../widgets/rbi_forex_card.dart';
import '../../widgets/skeleton_loader.dart';
import '../../widgets/status_badge.dart';
import '../workspace/invoice_workspace_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  String _selectedStatusFilter = 'ALL';
  String _searchQuery = '';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<InvoiceProvider>(context, listen: false).fetchDashboardData();
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final invProvider = Provider.of<InvoiceProvider>(context);
    final metrics = invProvider.metrics;
    final currencyFormat = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);

    final isMobile = MediaQuery.of(context).size.width < 700;

    // Filter invoices requiring attention:
    // 1. Pending review / processing
    // 2. Failed / Error status
    // 3. TDS threshold exceeded or special compliance flags
    final attentionInvoices = invProvider.invoices.where((inv) {
      final disp = inv.displayStatus.toLowerCase();
      final isPending = disp == 'pending' || disp == 'processing' || inv.needsReview;
      final isFailed = disp == 'failed';
      return isPending || isFailed;
    }).toList();

    final filteredInvoices = invProvider.invoices.where((inv) {
      final matchesStatus = _selectedStatusFilter == 'ALL' ||
          inv.status.toUpperCase() == _selectedStatusFilter ||
          inv.displayStatus.toUpperCase() == _selectedStatusFilter ||
          (_selectedStatusFilter == 'PENDING' && inv.displayStatus.toLowerCase() == 'pending') ||
          (_selectedStatusFilter == 'APPROVED' && inv.displayStatus.toLowerCase() == 'approved') ||
          (_selectedStatusFilter == 'EXPORTED' && inv.displayStatus.toLowerCase() == 'exported');

      final vendor = inv.extractedData?.vendorName?.toLowerCase() ?? '';
      final invNum = inv.extractedData?.invoiceNumber?.toLowerCase() ?? (inv.filename?.toLowerCase() ?? '');
      final matchesQuery = _searchQuery.isEmpty ||
          vendor.contains(_searchQuery.toLowerCase()) ||
          invNum.contains(_searchQuery.toLowerCase());

      return matchesStatus && matchesQuery;
    }).toList();

    final totalCount = metrics.totalInvoices > 0 ? metrics.totalInvoices : invProvider.invoices.length;
    final exportedCount = metrics.exportedZoho > 0
        ? metrics.exportedZoho
        : invProvider.invoices.where((i) => i.displayStatus == 'exported' || (i.zohoBillId != null && i.zohoBillId!.isNotEmpty)).length;

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: RefreshIndicator(
        onRefresh: () => invProvider.fetchDashboardData(),
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: EdgeInsets.symmetric(
            horizontal: isMobile ? 16 : 28,
            vertical: isMobile ? 16 : 22,
          ),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1300),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Top: Financial Intelligence Banner & AI Engine Status
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    crossAxisAlignment: CrossAxisAlignment.center,
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Text(
                                  'Financial Intelligence',
                                  style: TextStyle(
                                    fontSize: isMobile ? 20 : 24,
                                    fontWeight: FontWeight.w800,
                                    letterSpacing: -0.5,
                                    color: isDark ? Colors.white : const Color(0xFF0F172A),
                                  ),
                                ),
                                const SizedBox(width: 12),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: isDark
                                        ? const Color(0xFF8B5CF6).withValues(alpha: 0.18)
                                        : const Color(0xFFF3E8FF),
                                    borderRadius: BorderRadius.circular(20),
                                    border: Border.all(
                                      color: isDark
                                          ? const Color(0xFF8B5CF6).withValues(alpha: 0.4)
                                          : const Color(0xFFDDD6FE),
                                    ),
                                  ),
                                  child: Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Container(
                                        width: 7,
                                        height: 7,
                                        decoration: const BoxDecoration(
                                          color: Color(0xFF7C3AED),
                                          shape: BoxShape.circle,
                                        ),
                                      ),
                                      const SizedBox(width: 6),
                                      const Text(
                                        'AI Engine: Active',
                                        style: TextStyle(
                                          fontSize: 11,
                                          fontWeight: FontWeight.w700,
                                          color: Color(0xFF7C3AED),
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Autonomous AP operations, statutory tax calculations & books sync',
                              style: TextStyle(
                                fontSize: 13,
                                color: isDark ? AppTheme.darkTextSecondary : AppTheme.lightTextSecondary,
                              ),
                            ),
                          ],
                        ),
                      ),
                      ElevatedButton.icon(
                        onPressed: () => invProvider.fetchDashboardData(),
                        icon: const Icon(Icons.refresh_rounded, size: 16),
                        label: const Text('Refresh'),
                        style: ElevatedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 18),

                  // KPI Cards: Compact, high-density cards
                  LayoutBuilder(
                    builder: (context, constraints) {
                      int crossAxisCount = constraints.maxWidth > 1050
                          ? 4
                          : constraints.maxWidth > 650
                              ? 2
                              : 1;

                      return GridView.count(
                        crossAxisCount: crossAxisCount,
                        crossAxisSpacing: 12,
                        mainAxisSpacing: 12,
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        childAspectRatio: crossAxisCount == 4
                            ? 2.35
                            : (crossAxisCount == 2 ? 2.15 : 2.6),
                        children: [
                          MetricCard(
                            title: 'Total Invoices',
                            value: totalCount.toString(),
                            subtitle: 'Recorded in database',
                            icon: Icons.receipt_long_rounded,
                            color: const Color(0xFF5B5BF7),
                          ),
                          MetricCard(
                            title: 'Pending Review',
                            value: metrics.pendingReview.toString(),
                            subtitle: 'Awaiting human sign-off',
                            icon: Icons.pending_actions_rounded,
                            color: const Color(0xFFF59E0B),
                          ),
                          MetricCard(
                            title: 'Exported to Zoho',
                            value: exportedCount.toString(),
                            subtitle: 'Synchronized to ledger',
                            icon: Icons.cloud_done_rounded,
                            color: const Color(0xFF10B981),
                          ),
                          MetricCard(
                            title: 'Processed Value',
                            value: currencyFormat.format(metrics.totalAmountProcessed),
                            subtitle: 'Gross invoice obligation',
                            icon: Icons.payments_rounded,
                            color: const Color(0xFF06B6D4),
                          ),
                        ],
                      );
                    },
                  ),
                  const SizedBox(height: 18),

                  // Live RBI Forex Rates & Currency Compliance Card
                  const RbiForexCard(),
                  const SizedBox(height: 20),

              // Prominent "NEEDS ATTENTION" Section
              _buildNeedsAttentionSection(
                context: context,
                invoices: attentionInvoices,
                currencyFormat: currencyFormat,
                isDark: isDark,
              ),
              const SizedBox(height: 24),

              // Recent Invoices Section Header
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        'Recent Invoices',
                        style: TextStyle(
                          fontSize: isMobile ? 18 : 20,
                          fontWeight: FontWeight.w800,
                          letterSpacing: -0.4,
                          color: isDark ? Colors.white : const Color(0xFF0F172A),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: isDark ? const Color(0xFF1E293B) : const Color(0xFFEEF2FF),
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(
                            color: isDark ? const Color(0xFF334155) : const Color(0xFFC7D2FE),
                          ),
                        ),
                        child: Text(
                          '${filteredInvoices.length} Invoices',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w700,
                            color: isDark ? AppTheme.primaryLight : const Color(0xFF4F46E5),
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: 14),

              // Search bar and Filter Chips Row
              Wrap(
                spacing: 10,
                runSpacing: 10,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  SizedBox(
                    width: isMobile ? double.infinity : 280,
                    child: TextField(
                      decoration: InputDecoration(
                        hintText: 'Search vendor or invoice #...',
                        prefixIcon: const Icon(Icons.search_rounded, size: 18),
                        isDense: true,
                        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(10),
                        ),
                      ),
                      style: const TextStyle(fontSize: 13),
                      onChanged: (val) {
                        setState(() {
                          _searchQuery = val;
                        });
                      },
                    ),
                  ),
                  _buildFilterChip('ALL', 'All Invoices', isDark),
                  _buildFilterChip('PENDING_REVIEW', 'Needs Review', isDark),
                  _buildFilterChip('EXPORTED_ZOHO', 'Exported Zoho', isDark),
                  _buildFilterChip('COMPLETED', 'Completed', isDark),
                ],
              ),
              const SizedBox(height: 16),

              // Invoices List Content
              if (invProvider.isLoading && invProvider.invoices.isEmpty)
                Column(
                  children: List.generate(4, (_) => const ListItemSkeleton()),
                )
              else if (filteredInvoices.isEmpty)
                GlassCard(
                  padding: const EdgeInsets.all(48),
                  child: Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: AppTheme.primaryColor.withValues(alpha: 0.1),
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(
                            Icons.receipt_long_outlined,
                            size: 40,
                            color: AppTheme.primaryLight,
                          ),
                        ),
                        const SizedBox(height: 16),
                        const Text(
                          'No Matching Invoices Found',
                          style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          'Try clearing filters or uploading a new invoice.',
                          style: TextStyle(
                            fontSize: 13,
                            color: isDark ? AppTheme.darkTextSecondary : AppTheme.lightTextSecondary,
                          ),
                        ),
                      ],
                    ),
                  ),
                )
              else
                ListView.separated(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: filteredInvoices.take(6).length,
                  separatorBuilder: (context, index) => const SizedBox(height: 10),
                  itemBuilder: (context, index) {
                    final inv = filteredInvoices[index];
                    final vendor = (inv.extractedData?.vendorName != null && inv.extractedData!.vendorName!.trim().isNotEmpty)
                        ? inv.extractedData!.vendorName!
                        : 'Unknown Vendor';
                    final invNum = (inv.extractedData?.invoiceNumber != null && inv.extractedData!.invoiceNumber!.trim().isNotEmpty)
                        ? inv.extractedData!.invoiceNumber!
                        : (inv.filename != null && inv.filename!.trim().isNotEmpty)
                            ? inv.filename!
                            : 'INV-#${inv.id}';
                    final total = inv.extractedData?.totalAmount ?? 0.0;
                    final date = inv.extractedData?.invoiceDate ??
                        (inv.createdAt != null
                            ? DateFormat('dd MMM yyyy').format(inv.createdAt!)
                            : '');

                    final tds = inv.tdsResult;
                    final isTds = tds?.applicable == true;
                    final isZoho = inv.displayStatus == 'exported';

                    return GlassCard(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      borderRadius: 12,
                      isInteractive: true,
                      onTap: () {
                        Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) => InvoiceWorkspaceScreen(invoiceId: inv.id),
                          ),
                        );
                      },
                      child: Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(8),
                            decoration: BoxDecoration(
                              color: const Color(0xFF5B5BF7).withValues(alpha: isDark ? 0.2 : 0.08),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: const Icon(
                              Icons.receipt_outlined,
                              color: Color(0xFF5B5BF7),
                              size: 18,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Text(
                                      invNum,
                                      style: TextStyle(
                                        fontWeight: FontWeight.w700,
                                        fontSize: 13.5,
                                        color: isDark ? Colors.white : const Color(0xFF0F172A),
                                      ),
                                    ),
                                    const SizedBox(width: 8),
                                    StatusBadge(status: inv.displayStatus, isSmall: true),
                                    if (isTds) ...[
                                      const SizedBox(width: 6),
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1.5),
                                        decoration: BoxDecoration(
                                          color: const Color(0xFFD97706).withValues(alpha: 0.12),
                                          borderRadius: BorderRadius.circular(4),
                                        ),
                                        child: Text(
                                          'TDS ${tds?.tdsSection ?? "194"}',
                                          style: const TextStyle(
                                            fontSize: 10,
                                            fontWeight: FontWeight.w700,
                                            color: Color(0xFFD97706),
                                          ),
                                        ),
                                      ),
                                    ],
                                    if (isZoho) ...[
                                      const SizedBox(width: 6),
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1.5),
                                        decoration: BoxDecoration(
                                          color: const Color(0xFF10B981).withValues(alpha: 0.12),
                                          borderRadius: BorderRadius.circular(4),
                                        ),
                                        child: const Text(
                                          '✓ Zoho',
                                          style: TextStyle(
                                            fontSize: 10,
                                            fontWeight: FontWeight.w700,
                                            color: Color(0xFF10B981),
                                          ),
                                        ),
                                      ),
                                    ],
                                  ],
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  vendor,
                                  style: TextStyle(
                                    fontSize: 11.5,
                                    fontWeight: FontWeight.w500,
                                    color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B),
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(width: 12),
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.end,
                            children: [
                              Text(
                                currencyFormat.format(total),
                                style: TextStyle(
                                  fontWeight: FontWeight.w800,
                                  fontSize: 14,
                                  color: isDark ? Colors.white : const Color(0xFF0F172A),
                                ),
                              ),
                              if (date.isNotEmpty)
                                Text(
                                  date,
                                  style: TextStyle(
                                    fontSize: 10.5,
                                    color: isDark ? const Color(0xFF64748B) : const Color(0xFF94A3B8),
                                  ),
                                ),
                            ],
                          ),
                          const SizedBox(width: 8),
                          const Icon(Icons.chevron_right_rounded, size: 18, color: Color(0xFF94A3B8)),
                        ],
                      ),
                    );
                  },
                ),
              ],
            ),
          ),
        ),
      ),
    ),
  );
}

  Widget _buildNeedsAttentionSection({
    required BuildContext context,
    required List<Invoice> invoices,
    required NumberFormat currencyFormat,
    required bool isDark,
  }) {
    if (invoices.isEmpty) {
      return GlassCard(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        borderRadius: 14,
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: const BoxDecoration(
                color: Color(0xFFECFDF5),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.check_circle_rounded, color: Color(0xFF059669), size: 20),
            ),
            const SizedBox(width: 14),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'All Invoices in Order',
                    style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
                  ),
                  SizedBox(height: 2),
                  Text(
                    'No pending exceptions, failed OCR parses, or TDS threshold warnings.',
                    style: TextStyle(fontSize: 12, color: Color(0xFF64748B)),
                  ),
                ],
              ),
            ),
          ],
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF1E1B4B).withValues(alpha: 0.3) : const Color(0xFFFFFBEB),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: isDark ? const Color(0xFFD97706).withValues(alpha: 0.5) : const Color(0xFFFDE68A),
          width: 1.2,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: const Color(0xFFD97706).withValues(alpha: 0.18),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(Icons.warning_amber_rounded, color: Color(0xFFD97706), size: 18),
                  ),
                  const SizedBox(width: 10),
                  Text(
                    'NEEDS ATTENTION (${invoices.length})',
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0.5,
                      color: isDark ? const Color(0xFFFBBF24) : const Color(0xFFB45309),
                    ),
                  ),
                ],
              ),
              Text(
                'Requires human sign-off before Zoho posting',
                style: TextStyle(
                  fontSize: 11.5,
                  color: isDark ? const Color(0xFFCBD5E1) : const Color(0xFF78350F),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ListView.separated(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: invoices.take(4).length,
            separatorBuilder: (context, index) => const SizedBox(height: 8),
            itemBuilder: (context, index) {
              final inv = invoices[index];
              final vendor = (inv.extractedData?.vendorName?.trim().isNotEmpty == true)
                  ? inv.extractedData!.vendorName!
                  : 'Vendor Verification Pending';
              final invNum = (inv.extractedData?.invoiceNumber?.trim().isNotEmpty == true)
                  ? inv.extractedData!.invoiceNumber!
                  : (inv.filename?.trim().isNotEmpty == true ? inv.filename! : 'INV-#${inv.id}');
              final total = inv.extractedData?.totalAmount ?? 0.0;
              final date = inv.extractedData?.invoiceDate ??
                  (inv.createdAt != null ? DateFormat('dd MMM yyyy').format(inv.createdAt!) : '');

              String alertReason = 'Pending financial review';
              if (inv.status.toUpperCase() == 'FAILED') {
                alertReason = 'OCR extraction failed — manual entry required';
              } else if (inv.tdsResult?.applicable == true) {
                alertReason = 'TDS Section ${inv.tdsResult?.tdsSection ?? "194J"} apply';
              } else if (inv.periodCategory == 'PREVIOUS_FINANCIAL_YEAR') {
                alertReason = 'Previous FY confirmation required';
              }

              return Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                decoration: BoxDecoration(
                  color: isDark ? const Color(0xFF0F172A) : Colors.white,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(
                    color: isDark ? const Color(0xFF334155) : const Color(0xFFF1F5F9),
                  ),
                ),
                child: Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: const Color(0xFF5B5BF7).withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Icon(Icons.receipt_long_outlined, size: 18, color: Color(0xFF5B5BF7)),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Text(
                                invNum,
                                style: TextStyle(
                                  fontWeight: FontWeight.w800,
                                  fontSize: 13.5,
                                  color: isDark ? Colors.white : const Color(0xFF0F172A),
                                ),
                              ),
                              const SizedBox(width: 8),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                decoration: BoxDecoration(
                                  color: const Color(0xFFD97706).withValues(alpha: 0.15),
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: Text(
                                  alertReason,
                                  style: const TextStyle(
                                    fontSize: 10.5,
                                    fontWeight: FontWeight.w700,
                                    color: Color(0xFFD97706),
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 2),
                          Text(
                            vendor,
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w500,
                              color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 14),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text(
                          currencyFormat.format(total),
                          style: TextStyle(
                            fontWeight: FontWeight.w800,
                            fontSize: 14,
                            color: isDark ? Colors.white : const Color(0xFF0F172A),
                          ),
                        ),
                        if (date.isNotEmpty)
                          Text(
                            date,
                            style: TextStyle(
                              fontSize: 11,
                              color: isDark ? const Color(0xFF64748B) : const Color(0xFF94A3B8),
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(width: 14),
                    ElevatedButton(
                      onPressed: () {
                        Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) => InvoiceWorkspaceScreen(invoiceId: inv.id),
                          ),
                        );
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF5B5BF7),
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                        textStyle: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
                      ),
                      child: const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text('Review'),
                          SizedBox(width: 4),
                          Icon(Icons.arrow_forward_rounded, size: 13),
                        ],
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
        ],
      ),
    );
  }


  Widget _buildFilterChip(String filterId, String label, bool isDark) {
    final isSelected = _selectedStatusFilter == filterId;
    return InkWell(
      onTap: () => setState(() => _selectedStatusFilter = filterId),
      borderRadius: BorderRadius.circular(20),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected
              ? const Color(0xFF5B5BF7)
              : (isDark ? const Color(0xFF1E293B) : Colors.white),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isSelected
                ? const Color(0xFF5B5BF7)
                : (isDark ? const Color(0xFF334155) : const Color(0xFFE2E8F0)),
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 12,
            fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
            color: isSelected
                ? Colors.white
                : (isDark ? const Color(0xFFE2E8F0) : const Color(0xFF475569)),
          ),
        ),
      ),
    );
  }
}
