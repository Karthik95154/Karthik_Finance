import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../../config/theme.dart';
import '../../models/invoice_models.dart';
import '../../providers/invoice_provider.dart';
import '../../widgets/glass_card.dart';
import '../../widgets/skeleton_loader.dart';
import '../../widgets/status_badge.dart';
import '../workspace/invoice_workspace_screen.dart';

class InvoiceListScreen extends StatefulWidget {
  const InvoiceListScreen({super.key});

  @override
  State<InvoiceListScreen> createState() => _InvoiceListScreenState();
}

class _InvoiceListScreenState extends State<InvoiceListScreen> {
  final _searchController = TextEditingController();
  final Set<dynamic> _selectedInvoiceIds = {};
  bool _isBulkExporting = false;

  final List<Map<String, String>> _statusFilters = const [
    {'id': 'all', 'label': 'All Invoices'},
    {'id': 'pending', 'label': 'Pending Review'},
    {'id': 'approved', 'label': 'Approved'},
    {'id': 'exported', 'label': 'Exported to Zoho'},
    {'id': 'failed', 'label': 'Failed'},
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<InvoiceProvider>(context, listen: false).fetchInvoices();
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final invProvider = Provider.of<InvoiceProvider>(context);
    final currencyFormat = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);
    final filtered = invProvider.filteredInvoices;
    final allInvoices = invProvider.invoices;

    final isMobile = MediaQuery.of(context).size.width < 750;

    // Calculate filter counts
    final pendingCount = allInvoices.where((i) => i.displayStatus == 'pending' || i.displayStatus == 'processing').length;
    final approvedCount = allInvoices.where((i) => i.displayStatus == 'approved').length;
    final exportedCount = allInvoices.where((i) => i.displayStatus == 'exported').length;
    final failedCount = allInvoices.where((i) => i.displayStatus == 'failed').length;
    final indianCount = allInvoices.where((i) => i.isIndian).length;
    final foreignCount = allInvoices.where((i) => i.isForeign).length;

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1280),
          child: Padding(
            padding: EdgeInsets.symmetric(
              horizontal: isMobile ? 16 : 28,
              vertical: isMobile ? 16 : 24,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Top Header Bar
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
                                'Invoice Directory',
                                style: TextStyle(
                                  fontSize: isMobile ? 22 : 26,
                                  fontWeight: FontWeight.w800,
                                  letterSpacing: -0.6,
                                  color: isDark ? Colors.white : const Color(0xFF0F172A),
                                ),
                              ),
                              const SizedBox(width: 10),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                decoration: BoxDecoration(
                                  color: const Color(0xFF6366F1).withValues(alpha: 0.12),
                                  borderRadius: BorderRadius.circular(12),
                                  border: Border.all(
                                    color: const Color(0xFF6366F1).withValues(alpha: 0.3),
                                    width: 1,
                                  ),
                                ),
                                child: Text(
                                  '${allInvoices.length} Total',
                                  style: const TextStyle(
                                    fontSize: 11,
                                    fontWeight: FontWeight.w700,
                                    color: Color(0xFF6366F1),
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'Manage extracted invoices, verify statutory compliance & post to Zoho Books',
                            style: TextStyle(
                              fontSize: 13,
                              color: isDark ? AppTheme.darkTextSecondary : AppTheme.lightTextSecondary,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 16),
                    OutlinedButton.icon(
                      onPressed: () => invProvider.fetchInvoices(),
                      icon: const Icon(Icons.refresh_rounded, size: 16),
                      label: const Text('Refresh'),
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                        side: BorderSide(
                          color: isDark ? const Color(0xFF334155) : const Color(0xFFCBD5E1),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 18),

                // Search Bar & Filter Strip
                Row(
                  children: [
                    Expanded(
                      child: TextFormField(
                        controller: _searchController,
                        decoration: InputDecoration(
                          hintText: 'Search by Invoice #, Vendor Name, or GSTIN...',
                          prefixIcon: const Icon(Icons.search_rounded, size: 20, color: Color(0xFF6366F1)),
                          suffixIcon: _searchController.text.isNotEmpty
                              ? IconButton(
                                  icon: const Icon(Icons.clear_rounded, size: 18),
                                  onPressed: () {
                                    _searchController.clear();
                                    invProvider.setSearchQuery('');
                                  },
                                )
                              : null,
                          filled: true,
                          fillColor: isDark ? const Color(0xFF131D33) : Colors.white,
                          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: BorderSide(
                              color: isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0),
                            ),
                          ),
                          enabledBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: BorderSide(
                              color: isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0),
                            ),
                          ),
                          focusedBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: const BorderSide(
                              color: Color(0xFF6366F1),
                              width: 1.5,
                            ),
                          ),
                        ),
                        onChanged: (val) => invProvider.setSearchQuery(val),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),

                // Origin Segmented Filter Tabs (All / Domestic GST / Foreign RCM)
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: [
                      _buildOriginFilterChip(
                        id: 'all',
                        label: 'All Sources',
                        icon: Icons.dashboard_outlined,
                        count: allInvoices.length,
                        invProvider: invProvider,
                        isDark: isDark,
                      ),
                      const SizedBox(width: 8),
                      _buildOriginFilterChip(
                        id: 'indian',
                        label: '🇮🇳 Domestic GST',
                        icon: Icons.account_balance_outlined,
                        count: indianCount,
                        invProvider: invProvider,
                        isDark: isDark,
                        activeColor: const Color(0xFF10B981),
                      ),
                      const SizedBox(width: 8),
                      _buildOriginFilterChip(
                        id: 'foreign',
                        label: '🌐 Foreign / RCM',
                        icon: Icons.public_rounded,
                        count: foreignCount,
                        invProvider: invProvider,
                        isDark: isDark,
                        activeColor: const Color(0xFF8B5CF6),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 10),

                // Status Filter Chips with Counts
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: _statusFilters.map((filter) {
                      final isSelected = invProvider.selectedStatus == filter['id'];
                      int count = allInvoices.length;
                      if (filter['id'] == 'pending') count = pendingCount;
                      if (filter['id'] == 'approved') count = approvedCount;
                      if (filter['id'] == 'exported') count = exportedCount;
                      if (filter['id'] == 'failed') count = failedCount;

                      return Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: InkWell(
                          onTap: () => invProvider.setFilterStatus(filter['id']!),
                          borderRadius: BorderRadius.circular(20),
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                            decoration: BoxDecoration(
                              color: isSelected
                                  ? const Color(0xFF6366F1)
                                  : (isDark ? const Color(0xFF131D33) : Colors.white),
                              borderRadius: BorderRadius.circular(20),
                              border: Border.all(
                                color: isSelected
                                    ? const Color(0xFF6366F1)
                                    : (isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0)),
                              ),
                              boxShadow: isSelected
                                  ? [
                                      BoxShadow(
                                        color: const Color(0xFF6366F1).withValues(alpha: 0.3),
                                        blurRadius: 8,
                                        offset: const Offset(0, 2),
                                      ),
                                    ]
                                  : null,
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text(
                                  filter['label']!,
                                  style: TextStyle(
                                    color: isSelected
                                        ? Colors.white
                                        : (isDark ? const Color(0xFFE2E8F0) : const Color(0xFF334155)),
                                    fontWeight: isSelected ? FontWeight.w700 : FontWeight.w600,
                                    fontSize: 12,
                                  ),
                                ),
                                const SizedBox(width: 6),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                                  decoration: BoxDecoration(
                                    color: isSelected
                                        ? Colors.white.withValues(alpha: 0.25)
                                        : (isDark ? const Color(0xFF1E293B) : const Color(0xFFF1F5F9)),
                                    borderRadius: BorderRadius.circular(10),
                                  ),
                                  child: Text(
                                    '$count',
                                    style: TextStyle(
                                      color: isSelected
                                          ? Colors.white
                                          : (isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
                                      fontSize: 11,
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      );
                    }).toList(),
                  ),
                ),
                const SizedBox(height: 8),

                // Origin (Indian vs Foreign) Pill Toggle
                Row(
                  children: [
                    _buildOriginFilterChip(
                      id: 'all',
                      label: 'All Origins',
                      count: allInvoices.length,
                      icon: Icons.all_inclusive_rounded,
                      invProvider: invProvider,
                      isDark: isDark,
                    ),
                    const SizedBox(width: 6),
                    _buildOriginFilterChip(
                      id: 'indian',
                      label: '🇮🇳 Indian',
                      count: indianCount,
                      icon: Icons.flag_rounded,
                      invProvider: invProvider,
                      isDark: isDark,
                      activeColor: const Color(0xFF10B981),
                    ),
                    const SizedBox(width: 6),
                    _buildOriginFilterChip(
                      id: 'foreign',
                      label: '🌐 Foreign',
                      count: foreignCount,
                      icon: Icons.public_rounded,
                      invProvider: invProvider,
                      isDark: isDark,
                      activeColor: const Color(0xFF6366F1),
                    ),
                  ],
                ),
                const SizedBox(height: 14),

                // Bulk Selection & Batch Actions Bar
                if (_selectedInvoiceIds.isNotEmpty) ...[
                  _buildBulkActionBar(context, invProvider, filtered, isDark),
                  const SizedBox(height: 12),
                ],

                // Invoices List
                Expanded(
                  child: invProvider.isLoading
                      ? ListView.builder(
                          itemCount: 6,
                          itemBuilder: (_, __) => const ListItemSkeleton(),
                        )
                      : filtered.isEmpty
                          ? GlassCard(
                              padding: const EdgeInsets.all(48),
                              child: Center(
                                child: Column(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Container(
                                      padding: const EdgeInsets.all(16),
                                      decoration: BoxDecoration(
                                        color: const Color(0xFF6366F1).withValues(alpha: 0.1),
                                        shape: BoxShape.circle,
                                      ),
                                      child: const Icon(
                                        Icons.search_off_rounded,
                                        size: 36,
                                        color: Color(0xFF6366F1),
                                      ),
                                    ),
                                    const SizedBox(height: 14),
                                    Text(
                                      'No matching invoices found',
                                      style: TextStyle(
                                        fontSize: 16,
                                        fontWeight: FontWeight.w700,
                                        color: isDark ? Colors.white : const Color(0xFF0F172A),
                                      ),
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      'Try adjusting your search query or filter status.',
                                      style: TextStyle(
                                        fontSize: 13,
                                        color: isDark ? AppTheme.darkTextSecondary : const Color(0xFF64748B),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            )
                          : ListView.separated(
                              padding: const EdgeInsets.only(top: 2, bottom: 20),
                              itemCount: filtered.length,
                              separatorBuilder: (context, index) => const SizedBox(height: 10),
                              itemBuilder: (context, index) {
                                final inv = filtered[index];
                                final vendor = (inv.extractedData?.vendorName != null && inv.extractedData!.vendorName!.trim().isNotEmpty)
                                    ? inv.extractedData!.vendorName!
                                    : 'Vendor Pending';
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

                                final isZohoExported = inv.displayStatus == 'exported' || (inv.zohoBillId != null && inv.zohoBillId!.isNotEmpty);
                                final isTdsApplicable = inv.tdsResult?.applicable == true;
                                final tdsSec = inv.tdsResult?.tdsSection;

                                return Material(
                                  color: Colors.transparent,
                                  borderRadius: BorderRadius.circular(12),
                                  child: InkWell(
                                    borderRadius: BorderRadius.circular(12),
                                    onTap: () {
                                      Navigator.of(context).push(
                                        MaterialPageRoute(
                                          builder: (_) => InvoiceWorkspaceScreen(invoiceId: inv.id),
                                        ),
                                      );
                                    },
                                    hoverColor: (isDark ? const Color(0xFF6366F1) : const Color(0xFF6366F1)).withValues(alpha: 0.04),
                                    child: Container(
                                      padding: EdgeInsets.symmetric(
                                        horizontal: isMobile ? 14 : 18,
                                        vertical: isMobile ? 12 : 14,
                                      ),
                                      decoration: BoxDecoration(
                                        color: isDark ? const Color(0xFF111C33) : Colors.white,
                                        borderRadius: BorderRadius.circular(12),
                                        border: Border.all(
                                          color: isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0),
                                          width: 1,
                                        ),
                                        boxShadow: [
                                          BoxShadow(
                                            color: Colors.black.withValues(alpha: isDark ? 0.2 : 0.02),
                                            blurRadius: 6,
                                            offset: const Offset(0, 2),
                                          ),
                                        ],
                                      ),
                                      child: Row(
                                        crossAxisAlignment: CrossAxisAlignment.center,
                                        children: [
                                          // Checkbox for Multi-Select
                                          Checkbox(
                                            value: _selectedInvoiceIds.contains(inv.id),
                                            onChanged: (bool? checked) {
                                              setState(() {
                                                if (checked == true) {
                                                  _selectedInvoiceIds.add(inv.id);
                                                } else {
                                                  _selectedInvoiceIds.remove(inv.id);
                                                }
                                              });
                                            },
                                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(4)),
                                            activeColor: const Color(0xFF6366F1),
                                          ),
                                          const SizedBox(width: 4),

                                          // Left Icon Box
                                          Container(
                                            width: 42,
                                            height: 42,
                                            decoration: BoxDecoration(
                                              gradient: LinearGradient(
                                                colors: isDark
                                                    ? [const Color(0xFF1E293B), const Color(0xFF0F172A)]
                                                    : [const Color(0xFFEEF2FF), const Color(0xFFE0E7FF)],
                                                begin: Alignment.topLeft,
                                                end: Alignment.bottomRight,
                                              ),
                                              borderRadius: BorderRadius.circular(10),
                                              border: Border.all(
                                                color: isDark
                                                    ? const Color(0xFF334155)
                                                    : const Color(0xFFC7D2FE),
                                                width: 1,
                                              ),
                                            ),
                                            child: const Icon(
                                              Icons.receipt_long_rounded,
                                              color: Color(0xFF6366F1),
                                              size: 20,
                                            ),
                                          ),
                                          const SizedBox(width: 14),

                                          // Center Column: Invoice #, Vendor, Meta Badges
                                          Expanded(
                                            child: Column(
                                              crossAxisAlignment: CrossAxisAlignment.start,
                                              mainAxisSize: MainAxisSize.min,
                                              children: [
                                                Row(
                                                  children: [
                                                    Flexible(
                                                      child: Text(
                                                        invNum,
                                                        style: TextStyle(
                                                          fontWeight: FontWeight.w800,
                                                          fontSize: 15,
                                                          letterSpacing: -0.2,
                                                          color: isDark ? Colors.white : const Color(0xFF0F172A),
                                                        ),
                                                        maxLines: 1,
                                                        overflow: TextOverflow.ellipsis,
                                                      ),
                                                    ),
                                                    const SizedBox(width: 8),
                                                    StatusBadge(
                                                      status: inv.displayStatus,
                                                      isSmall: true,
                                                    ),
                                                    const SizedBox(width: 6),
                                                    _buildOriginChip(inv, isDark),
                                                    if (isZohoExported) ...[
                                                      const SizedBox(width: 6),
                                                      Container(
                                                        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                                                        decoration: BoxDecoration(
                                                          color: isDark
                                                              ? const Color(0xFF10B981).withValues(alpha: 0.15)
                                                              : const Color(0xFFECFDF5),
                                                          borderRadius: BorderRadius.circular(6),
                                                          border: Border.all(
                                                            color: isDark
                                                                ? const Color(0xFF10B981).withValues(alpha: 0.3)
                                                                : const Color(0xFFA7F3D0),
                                                          ),
                                                        ),
                                                        child: Row(
                                                          mainAxisSize: MainAxisSize.min,
                                                          children: [
                                                            const Icon(Icons.cloud_done_rounded, size: 11, color: Color(0xFF10B981)),
                                                            const SizedBox(width: 3),
                                                            Text(
                                                              inv.zohoBillId != null && inv.zohoBillId!.isNotEmpty
                                                                  ? 'Bill #${inv.zohoBillId}'
                                                                  : 'Zoho Synced',
                                                              style: const TextStyle(
                                                                fontSize: 10.5,
                                                                fontWeight: FontWeight.w700,
                                                                color: Color(0xFF10B981),
                                                              ),
                                                            ),
                                                          ],
                                                        ),
                                                      ),
                                                    ],
                                                    if (isTdsApplicable) ...[
                                                      const SizedBox(width: 6),
                                                      Container(
                                                        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                                                        decoration: BoxDecoration(
                                                          color: isDark
                                                              ? const Color(0xFFF59E0B).withValues(alpha: 0.15)
                                                              : const Color(0xFFFEF3C7),
                                                          borderRadius: BorderRadius.circular(6),
                                                          border: Border.all(
                                                            color: isDark
                                                                ? const Color(0xFFF59E0B).withValues(alpha: 0.3)
                                                                : const Color(0xFFFDE68A),
                                                          ),
                                                        ),
                                                        child: Text(
                                                          tdsSec != null ? 'TDS u/s $tdsSec' : 'TDS Applicable',
                                                          style: const TextStyle(
                                                            fontSize: 10.5,
                                                            fontWeight: FontWeight.w700,
                                                            color: Color(0xFFD97706),
                                                          ),
                                                        ),
                                                      ),
                                                    ],
                                                  ],
                                                ),
                                                const SizedBox(height: 3),
                                                Row(
                                                  children: [
                                                    Flexible(
                                                      child: Text(
                                                        vendor,
                                                        style: TextStyle(
                                                          fontSize: 12.5,
                                                          fontWeight: FontWeight.w600,
                                                          color: isDark
                                                              ? AppTheme.darkTextSecondary
                                                              : const Color(0xFF475569),
                                                        ),
                                                        maxLines: 1,
                                                        overflow: TextOverflow.ellipsis,
                                                      ),
                                                    ),
                                                    if (date.isNotEmpty) ...[
                                                      Padding(
                                                        padding: const EdgeInsets.symmetric(horizontal: 6),
                                                        child: Text(
                                                          '•',
                                                          style: TextStyle(
                                                            color: isDark ? const Color(0xFF475569) : const Color(0xFF94A3B8),
                                                            fontSize: 11,
                                                          ),
                                                        ),
                                                      ),
                                                      Text(
                                                        date,
                                                        style: TextStyle(
                                                          fontSize: 11.5,
                                                          color: isDark
                                                              ? AppTheme.darkTextMuted
                                                              : const Color(0xFF64748B),
                                                        ),
                                                      ),
                                                    ],
                                                  ],
                                                ),
                                              ],
                                            ),
                                          ),
                                          const SizedBox(width: 16),

                                          // Right Column: Formatted Amount & Action Button
                                          Row(
                                            mainAxisSize: MainAxisSize.min,
                                            crossAxisAlignment: CrossAxisAlignment.center,
                                            children: [
                                              Column(
                                                crossAxisAlignment: CrossAxisAlignment.end,
                                                mainAxisSize: MainAxisSize.min,
                                                children: [
                                                  Text(
                                                    currencyFormat.format(total),
                                                    style: TextStyle(
                                                      fontWeight: FontWeight.w800,
                                                      fontSize: isMobile ? 15 : 16.5,
                                                      letterSpacing: -0.3,
                                                      color: isDark ? Colors.white : const Color(0xFF0F172A),
                                                    ),
                                                  ),
                                                  if ((inv.invoiceOrigin == 'FOREIGN_SERVICE' || (inv.originalCurrency != null && inv.originalCurrency != 'INR')) && (inv.originalTotalAmount != null || inv.extractedData?.originalTotalAmount != null || (inv.extractedData?.currency != null && inv.extractedData?.currency != 'INR'))) ...[
                                                    const SizedBox(height: 2),
                                                    Container(
                                                      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                                                      decoration: BoxDecoration(
                                                        color: const Color(0xFF0284C7).withOpacity(0.15),
                                                        borderRadius: BorderRadius.circular(4),
                                                      ),
                                                      child: Text(
                                                        '${inv.originalCurrency ?? inv.extractedData?.currency ?? 'USD'} ${NumberFormat('#,##0.00').format(inv.originalTotalAmount ?? inv.extractedData?.originalTotalAmount ?? inv.extractedData?.totalAmount ?? 0.0)}',
                                                        style: const TextStyle(
                                                          fontSize: 10,
                                                          fontWeight: FontWeight.w700,
                                                          color: Color(0xFF38BDF8),
                                                        ),
                                                      ),
                                                    ),
                                                  ] else if (inv.confidenceScore != null && inv.confidenceScore! > 0) ...[
                                                    const SizedBox(height: 2),
                                                    Text(
                                                      '${(inv.confidenceScore! * 100).toInt()}% AI Conf.',
                                                      style: TextStyle(
                                                        fontSize: 10.5,
                                                        fontWeight: FontWeight.w600,
                                                        color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B),
                                                      ),
                                                    ),
                                                  ],
                                                ],
                                              ),
                                              const SizedBox(width: 14),
                                              Container(
                                                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                                decoration: BoxDecoration(
                                                  color: const Color(0xFF6366F1),
                                                  borderRadius: BorderRadius.circular(8),
                                                  boxShadow: [
                                                    BoxShadow(
                                                      color: const Color(0xFF6366F1).withValues(alpha: 0.25),
                                                      blurRadius: 6,
                                                      offset: const Offset(0, 2),
                                                    ),
                                                  ],
                                                ),
                                                child: Row(
                                                  mainAxisSize: MainAxisSize.min,
                                                  children: [
                                                    Text(
                                                      isZohoExported ? 'View' : 'Review',
                                                      style: const TextStyle(
                                                        color: Colors.white,
                                                        fontSize: 11.5,
                                                        fontWeight: FontWeight.w700,
                                                      ),
                                                    ),
                                                    const SizedBox(width: 4),
                                                    const Icon(
                                                      Icons.arrow_forward_rounded,
                                                      size: 13,
                                                      color: Colors.white,
                                                    ),
                                                  ],
                                                ),
                                              ),
                                            ],
                                          ),
                                        ],
                                      ),
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
      ),
    );
  }

  Widget _buildOriginFilterChip({
    required String id,
    required String label,
    required int count,
    required IconData icon,
    required InvoiceProvider invProvider,
    required bool isDark,
    Color? activeColor,
  }) {
    final isSelected = invProvider.selectedOrigin == id;
    final color = activeColor ?? const Color(0xFF6366F1);

    return InkWell(
      onTap: () => invProvider.setOriginFilter(id),
      borderRadius: BorderRadius.circular(16),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: isSelected ? color.withValues(alpha: 0.18) : (isDark ? const Color(0xFF131D33) : Colors.white),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isSelected ? color : (isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0)),
            width: isSelected ? 1.2 : 1.0,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 13,
              color: isSelected ? color : (isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
            ),
            const SizedBox(width: 5),
            Text(
              label,
              style: TextStyle(
                fontSize: 11.5,
                fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                color: isSelected
                    ? (isDark ? Colors.white : const Color(0xFF0F172A))
                    : (isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
              ),
            ),
            const SizedBox(width: 5),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
              decoration: BoxDecoration(
                color: isSelected ? color : (isDark ? const Color(0xFF1E293B) : const Color(0xFFF1F5F9)),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                '$count',
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                  color: isSelected ? Colors.white : (isDark ? Colors.white70 : const Color(0xFF334155)),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildOriginChip(Invoice inv, bool isDark) {
    final isForeign = inv.isForeign;
    final color = isForeign ? const Color(0xFF6366F1) : const Color(0xFF10B981);
    final label = isForeign ? 'Foreign (${inv.currency ?? "USD"})' : 'Indian';

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            isForeign ? Icons.public_rounded : Icons.flag_rounded,
            size: 11,
            color: color,
          ),
          const SizedBox(width: 3.5),
          Text(
            label,
            style: TextStyle(
              fontSize: 10.5,
              fontWeight: FontWeight.w700,
              color: color,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBulkActionBar(BuildContext context, InvoiceProvider invProv, List<Invoice> filtered, bool isDark) {
    final selectedCount = _selectedInvoiceIds.length;
    final allSelected = filtered.isNotEmpty && filtered.every((i) => _selectedInvoiceIds.contains(i.id));

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF1E293B) : const Color(0xFFEEF2FF),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isDark ? const Color(0xFF334155) : const Color(0xFFC7D2FE),
        ),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              Checkbox(
                value: allSelected,
                onChanged: (checked) {
                  setState(() {
                    if (checked == true) {
                      _selectedInvoiceIds.addAll(filtered.map((e) => e.id));
                    } else {
                      _selectedInvoiceIds.clear();
                    }
                  });
                },
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(4)),
                activeColor: const Color(0xFF6366F1),
              ),
              const SizedBox(width: 8),
              Text(
                '$selectedCount selected',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.bold,
                  color: isDark ? Colors.white : const Color(0xFF0F172A),
                ),
              ),
            ],
          ),
          Row(
            children: [
              TextButton(
                onPressed: () => setState(() => _selectedInvoiceIds.clear()),
                child: const Text('Clear', style: TextStyle(fontSize: 12)),
              ),
              const SizedBox(width: 8),
              ElevatedButton.icon(
                onPressed: _isBulkExporting ? null : () => _handleBulkExport(invProv),
                icon: _isBulkExporting
                    ? const SizedBox(width: 12, height: 12, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Icon(Icons.cloud_upload_outlined, size: 14),
                label: Text(_isBulkExporting ? 'Exporting...' : 'Export Selected to Zoho'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF6366F1),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                  textStyle: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _handleBulkExport(InvoiceProvider invProv) async {
    if (_selectedInvoiceIds.isEmpty) return;
    setState(() => _isBulkExporting = true);
    int successCount = 0;
    int failCount = 0;

    for (final id in _selectedInvoiceIds.toList()) {
      try {
        await invProv.loadInvoiceDetail(id, silent: true);
        final ok = await invProv.exportToZoho();
        if (ok) {
          successCount++;
        } else {
          failCount++;
        }
      } catch (_) {
        failCount++;
      }
    }

    if (mounted) {
      setState(() {
        _isBulkExporting = false;
        _selectedInvoiceIds.clear();
      });
      invProv.fetchInvoices();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Bulk export complete: $successCount exported, $failCount failed'),
          backgroundColor: failCount == 0 ? const Color(0xFF10B981) : const Color(0xFFF59E0B),
        ),
      );
    }
  }
}

