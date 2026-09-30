import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../config/theme.dart';
import '../models/invoice_models.dart';
import 'glass_card.dart';

class LineItemTableWidget extends StatefulWidget {
  final List<LineItem> lineItems;
  final Function(int index, LineItem item) onUpdate;
  final VoidCallback onAdd;
  final Function(int index) onDelete;
  final bool isRcm;
  final String? invoiceOrigin;
  final List<String>? masterAccountNames;

  const LineItemTableWidget({
    super.key,
    required this.lineItems,
    required this.onUpdate,
    required this.onAdd,
    required this.onDelete,
    this.isRcm = false,
    this.invoiceOrigin,
    this.masterAccountNames,
  });

  @override
  State<LineItemTableWidget> createState() => _LineItemTableWidgetState();
}

class _LineItemTableWidgetState extends State<LineItemTableWidget> {
  final ScrollController _horizontalScrollController = ScrollController();
  bool _canScrollLeft = false;
  bool _canScrollRight = false;

  @override
  void initState() {
    super.initState();
    _horizontalScrollController.addListener(_updateScrollMetrics);
    WidgetsBinding.instance.addPostFrameCallback((_) => _updateScrollMetrics());
  }

  void _updateScrollMetrics() {
    if (!_horizontalScrollController.hasClients) return;
    final maxExt = _horizontalScrollController.position.maxScrollExtent;
    final offset = _horizontalScrollController.offset;
    if (mounted) {
      setState(() {
        _canScrollLeft = offset > 5;
        _canScrollRight = maxExt > 0 && offset < (maxExt - 5);
      });
    }
  }

  @override
  void dispose() {
    _horizontalScrollController.removeListener(_updateScrollMetrics);
    _horizontalScrollController.dispose();
    super.dispose();
  }

  void _scrollToStart() {
    if (!_horizontalScrollController.hasClients) return;
    _horizontalScrollController.animateTo(
      0.0,
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeOutCubic,
    );
  }

  void _scrollToEnd() {
    if (!_horizontalScrollController.hasClients) return;
    _horizontalScrollController.animateTo(
      _horizontalScrollController.position.maxScrollExtent,
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeOutCubic,
    );
  }

  void _scrollLeft() {
    if (!_horizontalScrollController.hasClients) return;
    _horizontalScrollController.animateTo(
      (_horizontalScrollController.offset - 280).clamp(0.0, _horizontalScrollController.position.maxScrollExtent),
      duration: const Duration(milliseconds: 250),
      curve: Curves.easeOutCubic,
    );
  }

  void _scrollRight() {
    if (!_horizontalScrollController.hasClients) return;
    _horizontalScrollController.animateTo(
      (_horizontalScrollController.offset + 280).clamp(0.0, _horizontalScrollController.position.maxScrollExtent),
      duration: const Duration(milliseconds: 250),
      curve: Curves.easeOutCubic,
    );
  }

  void _handlePointerSignal(PointerSignalEvent event) {
    if (event is PointerScrollEvent && _horizontalScrollController.hasClients) {
      final maxExt = _horizontalScrollController.position.maxScrollExtent;
      if (maxExt <= 0) return;

      // Translate mouse wheel (vertical scrollDelta.dy or horizontal scrollDelta.dx) to horizontal table slide
      final delta = event.scrollDelta.dx != 0 ? event.scrollDelta.dx : event.scrollDelta.dy;
      if (delta != 0) {
        final current = _horizontalScrollController.offset;
        final target = (current + delta).clamp(0.0, maxExt);
        if (current != target) {
          _horizontalScrollController.jumpTo(target);
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final currencyFormat = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);
    final lineItems = widget.lineItems;

    // Calculate live aggregated totals
    double totalTaxable = 0;
    double totalTax = 0;
    double grandTotal = 0;

    for (final item in lineItems) {
      final qty = item.quantity ?? 1.0;
      final price = item.unitPrice ?? item.rate ?? 0.0;
      final taxable = (item.taxableAmount != null && item.taxableAmount! > 0)
          ? item.taxableAmount!
          : (qty * price);
      final rawGst = item.gstRate;
      final gstRate = (rawGst != null && rawGst > 0)
          ? rawGst
          : (widget.isRcm ? 18.0 : (rawGst ?? 18.0));
      final tax = (item.cgstAmount ?? 0) + (item.sgstAmount ?? 0) + (item.igstAmount ?? 0) > 0
          ? ((item.cgstAmount ?? 0) + (item.sgstAmount ?? 0) + (item.igstAmount ?? 0))
          : (taxable * (gstRate / 100));
      final tot = (taxable + tax);

      totalTaxable += taxable;
      totalTax += tax;
      grandTotal += tot;
    }

    return GlassCard(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header with Add Item & Horizontal Mouse Slide Navigation Controls
          Wrap(
            alignment: WrapAlignment.spaceBetween,
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 12,
            runSpacing: 8,
            children: [
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    padding: const EdgeInsets.all(7),
                    decoration: BoxDecoration(
                      color: AppTheme.primaryColor.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(
                      Icons.table_chart_rounded,
                      size: 18,
                      color: AppTheme.primaryLight,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Text(
                    'Line Items & GST Schedule (${lineItems.length})',
                    style: TextStyle(
                      fontSize: 15.5,
                      fontWeight: FontWeight.w700,
                      color: isDark ? Colors.white : const Color(0xFF0F172A),
                    ),
                  ),
                ],
              ),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Quick Slide to start / end chips for mouse users
                  if (lineItems.isNotEmpty) ...[
                    InkWell(
                      onTap: _scrollToStart,
                      borderRadius: BorderRadius.circular(6),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: !_canScrollLeft
                              ? (isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.04))
                              : (isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0)),
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(
                            color: isDark ? Colors.white12 : Colors.black12,
                          ),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.first_page_rounded, size: 14, color: _canScrollLeft ? AppTheme.primaryLight : Colors.grey),
                            const SizedBox(width: 2),
                            Text(
                              'Items',
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                color: _canScrollLeft ? (isDark ? Colors.white : const Color(0xFF0F172A)) : Colors.grey,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(width: 6),
                    InkWell(
                      onTap: _scrollToEnd,
                      borderRadius: BorderRadius.circular(6),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: !_canScrollRight
                              ? (isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.04))
                              : (isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0)),
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(
                            color: isDark ? Colors.white12 : Colors.black12,
                          ),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text(
                              'Totals',
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                color: _canScrollRight ? (isDark ? Colors.white : const Color(0xFF0F172A)) : Colors.grey,
                              ),
                            ),
                            const SizedBox(width: 2),
                            Icon(Icons.last_page_rounded, size: 14, color: _canScrollRight ? AppTheme.primaryLight : Colors.grey),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                  ],
                  // Mouse Navigation Chevrons for sliding horizontal table
                  Container(
                    decoration: BoxDecoration(
                      color: isDark ? const Color(0xFF1E293B) : const Color(0xFFF1F5F9),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: isDark ? const Color(0xFF334155) : const Color(0xFFCBD5E1),
                      ),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        IconButton(
                          icon: Icon(
                            Icons.chevron_left_rounded,
                            size: 18,
                            color: _canScrollLeft ? (isDark ? Colors.white : Colors.black87) : Colors.grey.withValues(alpha: 0.4),
                          ),
                          onPressed: _canScrollLeft ? _scrollLeft : null,
                          padding: const EdgeInsets.all(6),
                          constraints: const BoxConstraints(),
                          tooltip: 'Slide columns left (Mouse Wheel / Click)',
                        ),
                        Container(
                          width: 1,
                          height: 16,
                          color: isDark ? const Color(0xFF334155) : const Color(0xFFCBD5E1),
                        ),
                        IconButton(
                          icon: Icon(
                            Icons.chevron_right_rounded,
                            size: 18,
                            color: _canScrollRight ? (isDark ? Colors.white : Colors.black87) : Colors.grey.withValues(alpha: 0.4),
                          ),
                          onPressed: _canScrollRight ? _scrollRight : null,
                          padding: const EdgeInsets.all(6),
                          constraints: const BoxConstraints(),
                          tooltip: 'Slide columns right (Mouse Wheel / Click)',
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 10),
                  ElevatedButton.icon(
                    onPressed: widget.onAdd,
                    icon: const Icon(Icons.add_rounded, size: 16),
                    label: const Text('Add Item'),
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                      textStyle: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                    ),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 14),

          if (lineItems.isEmpty)
            Container(
              padding: const EdgeInsets.all(32),
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: isDark ? AppTheme.darkSurface : const Color(0xFFF8FAFC),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: isDark ? Colors.white12 : Colors.black12),
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    Icons.receipt_long_outlined,
                    size: 36,
                    color: isDark ? AppTheme.darkTextMuted : AppTheme.lightTextMuted,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'No line items extracted. Click "Add Item" to create one manually.',
                    style: TextStyle(
                      fontSize: 13,
                      color: isDark ? AppTheme.darkTextSecondary : AppTheme.lightTextSecondary,
                    ),
                  ),
                ],
              ),
            )
          else
            Listener(
              onPointerSignal: _handlePointerSignal,
              child: Scrollbar(
                controller: _horizontalScrollController,
                thumbVisibility: true,
                trackVisibility: true,
                interactive: true,
                thickness: 10,
                radius: const Radius.circular(5),
                child: SingleChildScrollView(
                  controller: _horizontalScrollController,
                  scrollDirection: Axis.horizontal,
                  physics: const BouncingScrollPhysics(parent: AlwaysScrollableScrollPhysics()),
                  padding: const EdgeInsets.only(bottom: 12),
                child: Theme(
                  data: Theme.of(context).copyWith(
                    dividerColor: isDark ? Colors.white12 : Colors.black12,
                  ),
                  child: DataTable(
                    headingRowColor: WidgetStateProperty.all(
                      isDark ? const Color(0xFF0F172A) : const Color(0xFFF1F5F9),
                    ),
                    horizontalMargin: 12,
                    columnSpacing: 14,
                    dataRowMinHeight: 56,
                    dataRowMaxHeight: 74,
                    columns: const [
                      DataColumn(label: Text('#', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12))),
                      DataColumn(label: Text('Description', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12))),
                      DataColumn(label: Text('Account', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12))),
                      DataColumn(label: Text('HSN/SAC', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12))),
                      DataColumn(label: Text('Qty', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12))),
                      DataColumn(label: Text('Unit', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12))),
                      DataColumn(label: Text('Rate (₹)', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12))),
                      DataColumn(label: Text('Disc (₹)', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12))),
                      DataColumn(label: Text('GST %', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12))),
                      DataColumn(label: Text('Taxable (₹)', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12))),
                      DataColumn(label: Text('Tax (₹)', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12))),
                      DataColumn(label: Text('Total (₹)', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12))),
                      DataColumn(label: Text('Actions', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12))),
                    ],
                    rows: List.generate(lineItems.length, (index) {
                      final item = lineItems[index];
                      final qty = item.quantity ?? 1.0;
                      var price = item.unitPrice ?? item.rate ?? 0.0;
                      final disc = item.discount ?? 0.0;
                      final taxable = (item.taxableAmount != null && item.taxableAmount! > 0)
                          ? item.taxableAmount!
                          : (qty * price - disc);

                      // Ensure price/rate and taxable amount are mathematically consistent:
                      // If quantity is 1 (or salary/duty line where extracted rate was per-person/duty but taxable is the full line total),
                      // price must equal taxable amount.
                      if (taxable > 0 && (qty == 1.0 || price == 0.0 || (qty > 0 && (qty * price - disc - taxable).abs() > 0.05))) {
                        price = (taxable + disc) / (qty > 0 ? qty : 1.0);
                        item.unitPrice = price;
                        item.rate = price;
                      }
                      final gstRate = item.gstRate ?? 18.0;
                      final totalItemTax = (item.cgstAmount ?? 0.0) +
                          (item.sgstAmount ?? 0.0) +
                          (item.igstAmount ?? 0.0) +
                          (item.cessAmount ?? 0.0);
                      final tax = totalItemTax > 0 ? totalItemTax : (taxable * (gstRate / 100));
                      final rowTotal = (taxable + tax);

                      // Derive account name fallback if not explicitly set
                      final defaultAccount = (item.accountName != null && item.accountName!.isNotEmpty)
                          ? item.accountName!
                          : (item.description != null && item.description!.toLowerCase().contains('cloud')
                              ? 'Cloud Infrastructure & Hosting'
                              : (item.description != null &&
                                      (item.description!.toLowerCase().contains('professional') ||
                                          item.description!.toLowerCase().contains('legal') ||
                                          item.description!.toLowerCase().contains('fee') ||
                                          item.description!.toLowerCase().contains('consulting'))
                                  ? 'Professional & Legal Charges'
                                  : (item.description != null && item.description!.toLowerCase().contains('software')
                                      ? 'Software & IT Subscriptions'
                                      : 'Operating Expense / Purchase')));

                      // Ensure item has accountName initialized
                      item.accountName ??= defaultAccount;

                      // Dynamic available GST rates
                      final standardRates = [0.0, 5.0, 12.0, 18.0, 28.0];
                      final availableRates = standardRates.contains(gstRate)
                          ? standardRates
                          : ([...standardRates, gstRate]..sort());

                      // Dynamic available account names
                      final standardAccounts = [
                        if (widget.masterAccountNames != null && widget.masterAccountNames!.isNotEmpty)
                          ...widget.masterAccountNames!
                        else ...[
                          'Operating Expense / Purchase',
                          'Professional & Legal Charges',
                          'Security & Facility Services',
                          'Software & IT Subscriptions',
                          'Cloud Infrastructure & Hosting',
                          'Rent & Occupancy Expenses',
                          'Repairs & Maintenance',
                          'Office Supplies & Stationery',
                          'Travel & Conveyance',
                          'Advertising & Marketing',
                          'Miscellaneous Expenses',
                        ]
                      ];
                      final currentAccount = item.accountName ?? defaultAccount;
                      final availableAccounts = standardAccounts.contains(currentAccount)
                          ? standardAccounts
                          : [currentAccount, ...standardAccounts];

                      return DataRow(
                        key: ValueKey('line_item_${index}_${item.description}_$qty-$price-$gstRate-${item.taxableAmount}-${item.total}'),
                        cells: [
                          DataCell(
                            Text(
                              '${index + 1}',
                              style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 12),
                            ),
                          ),
                          // 1. Description Field
                          DataCell(
                            SizedBox(
                              width: 170,
                              child: TextFormField(
                                initialValue: item.description ?? '',
                                decoration: InputDecoration(
                                  isDense: true,
                                  contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(6)),
                                ),
                                style: const TextStyle(fontSize: 12),
                                onChanged: (val) {
                                  item.description = val;
                                  widget.onUpdate(index, item);
                                },
                              ),
                            ),
                          ),
                          // 2. Account Dropdown
                          DataCell(
                            SizedBox(
                              width: 180,
                              child: DropdownButtonHideUnderline(
                                child: DropdownButton<String>(
                                  value: currentAccount,
                                  isExpanded: true,
                                  isDense: true,
                                  icon: const Icon(Icons.arrow_drop_down_rounded, size: 16),
                                  style: TextStyle(
                                    fontSize: 11.5,
                                    fontWeight: FontWeight.w600,
                                    color: isDark ? Colors.white : const Color(0xFF0F172A),
                                  ),
                                  dropdownColor: isDark ? const Color(0xFF1E293B) : Colors.white,
                                  items: availableAccounts.map((acc) {
                                    return DropdownMenuItem<String>(
                                      value: acc,
                                      child: Text(acc, overflow: TextOverflow.ellipsis),
                                    );
                                  }).toList(),
                                  onChanged: (val) {
                                    if (val != null) {
                                      item.accountName = val;
                                      widget.onUpdate(index, item);
                                    }
                                  },
                                ),
                              ),
                            ),
                          ),
                          // 3. HSN/SAC
                          DataCell(
                            SizedBox(
                              width: 80,
                              child: TextFormField(
                                initialValue: item.hsnCode ?? '',
                                decoration: InputDecoration(
                                  isDense: true,
                                  hintText: '998311',
                                  contentPadding: const EdgeInsets.symmetric(horizontal: 6, vertical: 6),
                                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(6)),
                                ),
                                style: const TextStyle(fontSize: 11.5),
                                onChanged: (val) {
                                  item.hsnCode = val;
                                  widget.onUpdate(index, item);
                                },
                              ),
                            ),
                          ),
                          // 4. Quantity
                          DataCell(
                            SizedBox(
                              width: 55,
                              child: TextFormField(
                                key: ValueKey('qty_${index}_$qty'),
                                initialValue: qty.toString(),
                                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                                decoration: InputDecoration(
                                  isDense: true,
                                  contentPadding: const EdgeInsets.symmetric(horizontal: 6, vertical: 6),
                                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(6)),
                                ),
                                style: const TextStyle(fontSize: 11.5),
                                onChanged: (val) {
                                  final newQty = double.tryParse(val) ?? 1.0;
                                  item.quantity = newQty;
                                  var p = item.unitPrice ?? item.rate ?? 0.0;
                                  if (p == 0.0 && item.taxableAmount != null && item.taxableAmount! > 0) {
                                    p = item.taxableAmount! / (newQty > 0 ? newQty : 1.0);
                                    item.unitPrice = p;
                                    item.rate = p;
                                  }
                                  item.taxableAmount = (newQty * p) - (item.discount ?? 0.0);
                                  final taxVal = item.taxableAmount! * ((item.gstRate ?? 18.0) / 100);
                                  if ((item.igstAmount ?? 0) > 0 || (item.igstRate ?? 0) > 0) {
                                    item.igstAmount = taxVal;
                                  } else {
                                    item.cgstAmount = taxVal / 2;
                                    item.sgstAmount = taxVal / 2;
                                  }
                                  item.total = item.taxableAmount! + taxVal;
                                  widget.onUpdate(index, item);
                                },
                              ),
                            ),
                          ),
                          // 5. Unit of Measure (UOM)
                          DataCell(
                            SizedBox(
                              width: 60,
                              child: TextFormField(
                                initialValue: item.unit ?? 'NOS',
                                decoration: InputDecoration(
                                  isDense: true,
                                  hintText: 'NOS',
                                  contentPadding: const EdgeInsets.symmetric(horizontal: 6, vertical: 6),
                                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(6)),
                                ),
                                style: const TextStyle(fontSize: 11.5),
                                onChanged: (val) {
                                  item.unit = val;
                                  widget.onUpdate(index, item);
                                },
                              ),
                            ),
                          ),
                          // 6. Rate / Unit Price (INR + Foreign Subtext)
                          DataCell(
                            Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                SizedBox(
                                  width: 90,
                                  child: TextFormField(
                                    key: ValueKey('price_${index}_$price'),
                                    initialValue: price > 0 ? price.toStringAsFixed(2) : (taxable > 0 ? taxable.toStringAsFixed(2) : '0.00'),
                                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                                    decoration: InputDecoration(
                                      isDense: true,
                                      contentPadding: const EdgeInsets.symmetric(horizontal: 6, vertical: 6),
                                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(6)),
                                    ),
                                    style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600),
                                    onChanged: (val) {
                                      final newPrice = double.tryParse(val) ?? 0.0;
                                      item.unitPrice = newPrice;
                                      item.rate = newPrice;
                                      item.taxableAmount = ((item.quantity ?? 1.0) * newPrice) - (item.discount ?? 0.0);
                                      final taxVal = item.taxableAmount! * ((item.gstRate ?? 18.0) / 100);
                                      if ((item.igstAmount ?? 0) > 0 || (item.igstRate ?? 0) > 0) {
                                        item.igstAmount = taxVal;
                                      } else {
                                        item.cgstAmount = taxVal / 2;
                                        item.sgstAmount = taxVal / 2;
                                      }
                                      item.total = item.taxableAmount! + taxVal;
                                      widget.onUpdate(index, item);
                                    },
                                  ),
                                ),
                                if (item.originalUnitPrice != null && item.originalUnitPrice! > 0)
                                  Padding(
                                    padding: const EdgeInsets.only(top: 2, left: 2),
                                    child: Text(
                                      '${item.originalCurrency ?? "USD"} ${item.originalUnitPrice!.toStringAsFixed(2)}',
                                      style: const TextStyle(fontSize: 9.5, color: Color(0xFF0284C7), fontWeight: FontWeight.w600),
                                    ),
                                  ),
                              ],
                            ),
                          ),
                          // 7. Discount
                          DataCell(
                            SizedBox(
                              width: 65,
                              child: TextFormField(
                                key: ValueKey('disc_${index}_$disc'),
                                initialValue: disc > 0 ? disc.toStringAsFixed(2) : '',
                                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                                decoration: InputDecoration(
                                  isDense: true,
                                  hintText: '0.00',
                                  contentPadding: const EdgeInsets.symmetric(horizontal: 6, vertical: 6),
                                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(6)),
                                ),
                                style: const TextStyle(fontSize: 11.5),
                                onChanged: (val) {
                                  final newDisc = double.tryParse(val) ?? 0.0;
                                  item.discount = newDisc;
                                  final p = item.unitPrice ?? item.rate ?? 0.0;
                                  final q = item.quantity ?? 1.0;
                                  item.taxableAmount = (q * p) - newDisc;
                                  final taxVal = item.taxableAmount! * ((item.gstRate ?? 18.0) / 100);
                                  if ((item.igstAmount ?? 0) > 0 || (item.igstRate ?? 0) > 0) {
                                    item.igstAmount = taxVal;
                                  } else {
                                    item.cgstAmount = taxVal / 2;
                                    item.sgstAmount = taxVal / 2;
                                  }
                                  item.total = item.taxableAmount! + taxVal;
                                  widget.onUpdate(index, item);
                                },
                              ),
                            ),
                          ),
                          // 8. GST Rate %
                          DataCell(
                            SizedBox(
                              width: 72,
                              child: DropdownButtonFormField<double>(
                                key: ValueKey('gst_${index}_$gstRate'),
                                initialValue: gstRate,
                                isDense: true,
                                decoration: InputDecoration(
                                  contentPadding: const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
                                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(6)),
                                ),
                                style: TextStyle(
                                  fontSize: 11.5,
                                  color: isDark ? Colors.white : Colors.black87,
                                ),
                                items: availableRates.map((r) {
                                  final label = r.truncateToDouble() == r ? '${r.toInt()}%' : '${r.toStringAsFixed(2)}%';
                                  return DropdownMenuItem<double>(
                                    value: r,
                                    child: Text(label),
                                  );
                                }).toList(),
                                onChanged: (newRate) {
                                  if (newRate != null) {
                                    item.gstRate = newRate;
                                    var p = item.unitPrice ?? item.rate ?? 0.0;
                                    if (p == 0.0 && item.taxableAmount != null && item.taxableAmount! > 0) {
                                      p = item.taxableAmount! / (qty > 0 ? qty : 1.0);
                                      item.unitPrice = p;
                                      item.rate = p;
                                    }
                                    final taxBase = (item.taxableAmount != null && item.taxableAmount! > 0)
                                        ? item.taxableAmount!
                                        : ((qty * p) - (item.discount ?? 0.0));
                                    item.taxableAmount = taxBase;
                                    final taxVal = taxBase * (newRate / 100);
                                    if (widget.isRcm || (item.igstAmount ?? 0) > 0 || (item.igstRate ?? 0) > 0) {
                                      item.igstRate = newRate;
                                      item.igstAmount = taxVal;
                                      item.cgstAmount = 0.0;
                                      item.sgstAmount = 0.0;
                                    } else {
                                      item.cgstRate = newRate / 2;
                                      item.sgstRate = newRate / 2;
                                      item.cgstAmount = taxVal / 2;
                                      item.sgstAmount = taxVal / 2;
                                      item.igstAmount = 0.0;
                                    }
                                    item.total = taxBase + taxVal;
                                    widget.onUpdate(index, item);
                                  }
                                },
                              ),
                            ),
                          ),
                          // 9. Editable Taxable Amount (INR + Foreign Subtext)
                          DataCell(
                            Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                SizedBox(
                                  width: 90,
                                  child: TextFormField(
                                    key: ValueKey('taxable_${index}_$taxable'),
                                    initialValue: taxable > 0 ? taxable.toStringAsFixed(2) : '0.00',
                                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                                    decoration: InputDecoration(
                                      isDense: true,
                                      contentPadding: const EdgeInsets.symmetric(horizontal: 6, vertical: 6),
                                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(6)),
                                    ),
                                    style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600),
                                    onChanged: (val) {
                                      final newTaxable = double.tryParse(val) ?? 0.0;
                                      item.taxableAmount = newTaxable;
                                      final taxVal = newTaxable * ((item.gstRate ?? 18.0) / 100);
                                      if ((item.igstAmount ?? 0) > 0 || (item.igstRate ?? 0) > 0) {
                                        item.igstAmount = taxVal;
                                      } else {
                                        item.cgstAmount = taxVal / 2;
                                        item.sgstAmount = taxVal / 2;
                                      }
                                      item.total = newTaxable + taxVal;
                                      widget.onUpdate(index, item);
                                    },
                                  ),
                                ),
                                if (item.originalTaxableAmount != null && item.originalTaxableAmount! > 0)
                                  Padding(
                                    padding: const EdgeInsets.only(top: 2, left: 2),
                                    child: Text(
                                      '${item.originalCurrency ?? "USD"} ${item.originalTaxableAmount!.toStringAsFixed(2)}',
                                      style: const TextStyle(fontSize: 9.5, color: Color(0xFF0284C7), fontWeight: FontWeight.w600),
                                    ),
                                  ),
                              ],
                            ),
                          ),
                          // 10. Editable Tax (GST)
                          DataCell(
                            SizedBox(
                              width: 80,
                              child: TextFormField(
                                key: ValueKey('tax_${index}_$tax'),
                                initialValue: tax > 0 ? tax.toStringAsFixed(2) : '0.00',
                                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                                decoration: InputDecoration(
                                  isDense: true,
                                  contentPadding: const EdgeInsets.symmetric(horizontal: 6, vertical: 6),
                                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(6)),
                                ),
                                style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600, color: AppTheme.secondaryColor),
                                onChanged: (val) {
                                  final newTax = double.tryParse(val) ?? 0.0;
                                  if ((item.igstAmount ?? 0) > 0 || (item.igstRate ?? 0) > 0) {
                                    item.igstAmount = newTax;
                                  } else {
                                    item.cgstAmount = newTax / 2;
                                    item.sgstAmount = newTax / 2;
                                  }
                                  item.total = (item.taxableAmount ?? taxable) + newTax;
                                  widget.onUpdate(index, item);
                                },
                              ),
                            ),
                          ),
                          // 11. Editable Row Total (INR + Foreign Subtext)
                          DataCell(
                            Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                SizedBox(
                                  width: 90,
                                  child: TextFormField(
                                    key: ValueKey('total_${index}_$rowTotal'),
                                    initialValue: rowTotal > 0 ? rowTotal.toStringAsFixed(2) : '0.00',
                                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                                    decoration: InputDecoration(
                                      isDense: true,
                                      contentPadding: const EdgeInsets.symmetric(horizontal: 6, vertical: 6),
                                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(6)),
                                    ),
                                    style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.bold, color: AppTheme.primaryLight),
                                    onChanged: (val) {
                                      final newTot = double.tryParse(val) ?? 0.0;
                                      item.total = newTot;
                                      widget.onUpdate(index, item);
                                    },
                                  ),
                                ),
                                () {
                                  final origTaxable = item.originalTaxableAmount ?? (item.originalUnitPrice != null ? (item.originalUnitPrice! * (item.quantity ?? 1.0)) : null);
                                  final itemRate = item.gstRate ?? (item.igstRate ?? ((item.cgstRate ?? 0) + (item.sgstRate ?? 0) > 0 ? (item.cgstRate ?? 0) + (item.sgstRate ?? 0) : 18.0));
                                  final foreignLineTotal = (origTaxable != null && origTaxable > 0)
                                      ? (origTaxable * (1.0 + (itemRate / 100.0)))
                                      : (item.originalTotal != null && item.originalTotal! > 0 ? item.originalTotal! : null);
                                  if (foreignLineTotal != null && foreignLineTotal > 0) {
                                    return Padding(
                                      padding: const EdgeInsets.only(top: 2, left: 2),
                                      child: Text(
                                        '${item.originalCurrency ?? "USD"} ${foreignLineTotal.toStringAsFixed(2)}',
                                        style: const TextStyle(fontSize: 9.5, color: Color(0xFF0284C7), fontWeight: FontWeight.w600),
                                      ),
                                    );
                                  }
                                  return const SizedBox.shrink();
                                }(),
                              ],
                            ),
                          ),
                          // 12. Actions: Edit Details Modal & Delete
                          DataCell(
                            Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                IconButton(
                                  icon: const Icon(Icons.edit_note_rounded, size: 18, color: Color(0xFF0284C7)),
                                  onPressed: () => _showEditLineItemDialog(context, index, item),
                                  tooltip: 'Open Full Line Item Editor',
                                ),
                                IconButton(
                                  icon: const Icon(Icons.delete_outline_rounded, size: 17, color: AppTheme.errorColor),
                                  onPressed: () => widget.onDelete(index),
                                  tooltip: 'Remove item',
                                ),
                              ],
                            ),
                          ),
                        ],
                      );
                    }),
                  ),
                ),
              ),
            ),
          ),

          const SizedBox(height: 14),

          // Aggregated Summary Bar
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: isDark ? AppTheme.darkSurface : const Color(0xFFF1F5F9),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: isDark ? Colors.white12 : Colors.black12),
            ),
            child: Wrap(
              alignment: WrapAlignment.spaceBetween,
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: 16,
              runSpacing: 8,
              children: [
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      'Subtotal (Taxable): ',
                      style: TextStyle(
                        fontSize: 12.5,
                        color: isDark ? AppTheme.darkTextSecondary : AppTheme.lightTextSecondary,
                      ),
                    ),
                    Text(
                      currencyFormat.format(totalTaxable),
                      style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
                    ),
                  ],
                ),
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      widget.isRcm ? 'RCM GST (18% IGST): ' : 'Total GST: ',
                      style: TextStyle(
                        fontSize: 12.5,
                        color: isDark ? AppTheme.darkTextSecondary : AppTheme.lightTextSecondary,
                      ),
                    ),
                    Text(
                      currencyFormat.format(totalTax),
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                        color: AppTheme.secondaryColor,
                      ),
                    ),
                    if (widget.isRcm)
                      Padding(
                        padding: const EdgeInsets.only(left: 6),
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
                          decoration: BoxDecoration(
                            color: const Color(0xFF10B981).withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: const Text('100% ITC Eligible', style: TextStyle(fontSize: 9.5, fontWeight: FontWeight.bold, color: Color(0xFF10B981))),
                        ),
                      ),
                  ],
                ),
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      'Grand Total: ',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                        color: isDark ? Colors.white : const Color(0xFF0F172A),
                      ),
                    ),
                    Text(
                      currencyFormat.format(grandTotal),
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w800,
                        color: AppTheme.primaryLight,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  void _showEditLineItemDialog(BuildContext context, int index, LineItem item) {
    final theme = Theme.of(context);

    // Local state copies for dialog editing
    final descCtrl = TextEditingController(text: item.description ?? '');
    final hsnCtrl = TextEditingController(text: item.hsnCode ?? '');
    final qtyCtrl = TextEditingController(text: (item.quantity ?? 1.0).toString());
    final unitCtrl = TextEditingController(text: item.unit ?? 'NOS');
    final priceCtrl = TextEditingController(text: (item.unitPrice ?? item.rate ?? 0.0).toStringAsFixed(2));
    final discCtrl = TextEditingController(text: (item.discount ?? 0.0) > 0 ? (item.discount!).toStringAsFixed(2) : '0.00');
    final taxableCtrl = TextEditingController(
      text: ((item.taxableAmount != null && item.taxableAmount! > 0)
              ? item.taxableAmount!
              : ((item.quantity ?? 1.0) * (item.unitPrice ?? item.rate ?? 0.0) - (item.discount ?? 0.0)))
          .toStringAsFixed(2),
    );
    final cgstCtrl = TextEditingController(text: (item.cgstAmount ?? 0.0).toStringAsFixed(2));
    final sgstCtrl = TextEditingController(text: (item.sgstAmount ?? 0.0).toStringAsFixed(2));
    final igstCtrl = TextEditingController(text: (item.igstAmount ?? 0.0).toStringAsFixed(2));
    final cessCtrl = TextEditingController(text: (item.cessAmount ?? 0.0).toStringAsFixed(2));
    final totalCtrl = TextEditingController(
      text: (item.total != null && item.total! > 0) ? item.total!.toStringAsFixed(2) : '0.00',
    );

    double currentGstRate = item.gstRate ?? 18.0;
    String currentAccount = item.accountName ?? 'Operating Expense / Purchase';

    final standardAccounts = [
      'Operating Expense / Purchase',
      'Professional & Legal Charges',
      'Security & Facility Services',
      'Software & IT Subscriptions',
      'Cloud Infrastructure & Hosting',
      'Rent & Occupancy Expenses',
      'Repairs & Maintenance',
      'Office Supplies & Stationery',
      'Travel & Conveyance',
      'Advertising & Marketing',
      'Miscellaneous Expenses',
    ];
    final availableAccounts = standardAccounts.contains(currentAccount)
        ? standardAccounts
        : [currentAccount, ...standardAccounts];

    showDialog(
      context: context,
      builder: (dialogCtx) => StatefulBuilder(
        builder: (context, setDialogState) {
          void autoCalc() {
            final q = double.tryParse(qtyCtrl.text) ?? 1.0;
            final p = double.tryParse(priceCtrl.text) ?? 0.0;
            final d = double.tryParse(discCtrl.text) ?? 0.0;
            final base = (q * p) - d;
            taxableCtrl.text = base.toStringAsFixed(2);

            final taxVal = base * (currentGstRate / 100);
            final isIgst = (double.tryParse(igstCtrl.text) ?? 0.0) > 0 || (item.igstRate ?? 0.0) > 0;
            if (isIgst) {
              igstCtrl.text = taxVal.toStringAsFixed(2);
              cgstCtrl.text = '0.00';
              sgstCtrl.text = '0.00';
            } else {
              cgstCtrl.text = (taxVal / 2).toStringAsFixed(2);
              sgstCtrl.text = (taxVal / 2).toStringAsFixed(2);
              igstCtrl.text = '0.00';
            }
            final cs = double.tryParse(cessCtrl.text) ?? 0.0;
            totalCtrl.text = (base + taxVal + cs).toStringAsFixed(2);
            setDialogState(() {});
          }

          return AlertDialog(
            title: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                    color: const Color(0xFF0284C7).withOpacity(0.15),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: const Icon(Icons.edit_document, size: 20, color: Color(0xFF0284C7)),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Edit Financial Line Item #${index + 1}', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                      Text('Modify quantity, statutory taxes, UOM, and assessable base with live verification', style: TextStyle(fontSize: 11, color: theme.textTheme.bodySmall?.color)),
                    ],
                  ),
                ),
              ],
            ),
            content: SizedBox(
              width: 650,
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (item.originalUnitPrice != null && item.originalUnitPrice! > 0) ...[
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        margin: const EdgeInsets.only(bottom: 12),
                        decoration: BoxDecoration(
                          color: const Color(0xFF0284C7).withOpacity(0.1),
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: const Color(0xFF0284C7).withOpacity(0.3)),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.currency_exchange_rounded, size: 14, color: Color(0xFF0284C7)),
                            const SizedBox(width: 6),
                            Text(
                              'Foreign Currency Line Item: ${item.originalCurrency ?? "USD"} ${item.originalUnitPrice!.toStringAsFixed(2)}  (Converted canonical value in INR below)',
                              style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: Color(0xFF0284C7)),
                            ),
                          ],
                        ),
                      ),
                    ],
                    // Row 1: Description & Account
                    Row(
                      children: [
                        Expanded(
                          flex: 3,
                          child: TextFormField(
                            controller: descCtrl,
                            decoration: const InputDecoration(labelText: 'Item Description / Particulars', border: OutlineInputBorder(), isDense: true),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          flex: 2,
                          child: DropdownButtonFormField<String>(
                            value: currentAccount,
                            isExpanded: true,
                            decoration: const InputDecoration(labelText: 'GL Expense Account', border: OutlineInputBorder(), isDense: true),
                            items: availableAccounts.map((a) => DropdownMenuItem(value: a, child: Text(a, style: const TextStyle(fontSize: 12), overflow: TextOverflow.ellipsis))).toList(),
                            onChanged: (v) {
                              if (v != null) setDialogState(() => currentAccount = v);
                            },
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    // Row 2: HSN, Qty, Unit, Rate, Discount
                    Row(
                      children: [
                        Expanded(
                          child: TextFormField(
                            controller: hsnCtrl,
                            decoration: const InputDecoration(labelText: 'HSN / SAC', border: OutlineInputBorder(), isDense: true),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: TextFormField(
                            controller: qtyCtrl,
                            keyboardType: const TextInputType.numberWithOptions(decimal: true),
                            decoration: const InputDecoration(labelText: 'Quantity', border: OutlineInputBorder(), isDense: true),
                            onChanged: (_) => autoCalc(),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: TextFormField(
                            controller: unitCtrl,
                            decoration: const InputDecoration(labelText: 'Unit (UOM)', hintText: 'NOS, PCS', border: OutlineInputBorder(), isDense: true),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          flex: 2,
                          child: TextFormField(
                            controller: priceCtrl,
                            keyboardType: const TextInputType.numberWithOptions(decimal: true),
                            decoration: const InputDecoration(labelText: 'Unit Rate (₹)', border: OutlineInputBorder(), isDense: true),
                            onChanged: (_) => autoCalc(),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: TextFormField(
                            controller: discCtrl,
                            keyboardType: const TextInputType.numberWithOptions(decimal: true),
                            decoration: const InputDecoration(labelText: 'Disc (₹)', border: OutlineInputBorder(), isDense: true),
                            onChanged: (_) => autoCalc(),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    // Row 3: Taxable Base, GST %, CGST, SGST, IGST, CESS
                    Row(
                      children: [
                        Expanded(
                          flex: 2,
                          child: TextFormField(
                            controller: taxableCtrl,
                            keyboardType: const TextInputType.numberWithOptions(decimal: true),
                            decoration: const InputDecoration(labelText: 'Taxable Amount (₹)', border: OutlineInputBorder(), isDense: true, prefixIcon: Icon(Icons.account_balance_wallet_outlined, size: 15)),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: DropdownButtonFormField<double>(
                            value: currentGstRate,
                            decoration: const InputDecoration(labelText: 'GST %', border: OutlineInputBorder(), isDense: true),
                            items: [0.0, 5.0, 12.0, 18.0, 28.0].map((r) => DropdownMenuItem(value: r, child: Text('${r.toInt()}%'))).toList(),
                            onChanged: (v) {
                              if (v != null) {
                                currentGstRate = v;
                                autoCalc();
                              }
                            },
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: TextFormField(
                            controller: cgstCtrl,
                            keyboardType: const TextInputType.numberWithOptions(decimal: true),
                            decoration: const InputDecoration(labelText: 'CGST (₹)', border: OutlineInputBorder(), isDense: true),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: TextFormField(
                            controller: sgstCtrl,
                            keyboardType: const TextInputType.numberWithOptions(decimal: true),
                            decoration: const InputDecoration(labelText: 'SGST (₹)', border: OutlineInputBorder(), isDense: true),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: TextFormField(
                            controller: igstCtrl,
                            keyboardType: const TextInputType.numberWithOptions(decimal: true),
                            decoration: const InputDecoration(labelText: 'IGST (₹)', border: OutlineInputBorder(), isDense: true),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: TextFormField(
                            controller: cessCtrl,
                            keyboardType: const TextInputType.numberWithOptions(decimal: true),
                            decoration: const InputDecoration(labelText: 'CESS (₹)', border: OutlineInputBorder(), isDense: true),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    // Row 4: Line Total & Math Helpers
                    Row(
                      children: [
                        Expanded(
                          child: TextFormField(
                            controller: totalCtrl,
                            keyboardType: const TextInputType.numberWithOptions(decimal: true),
                            decoration: const InputDecoration(labelText: 'Line Total Gross (₹)', border: OutlineInputBorder(), isDense: true, prefixIcon: Icon(Icons.payments_outlined, size: 15)),
                            style: const TextStyle(fontWeight: FontWeight.bold),
                          ),
                        ),
                        const SizedBox(width: 12),
                        OutlinedButton.icon(
                          onPressed: autoCalc,
                          icon: const Icon(Icons.auto_fix_high, size: 14),
                          label: const Text('Auto-Compute Math'),
                          style: OutlinedButton.styleFrom(padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12)),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialogCtx),
                child: const Text('Cancel'),
              ),
              ElevatedButton.icon(
                onPressed: () {
                  final updatedItem = LineItem(
                    lineIndex: item.lineIndex,
                    description: descCtrl.text,
                    accountName: currentAccount,
                    hsnCode: hsnCtrl.text,
                    quantity: double.tryParse(qtyCtrl.text) ?? 1.0,
                    unit: unitCtrl.text,
                    unitPrice: double.tryParse(priceCtrl.text) ?? 0.0,
                    rate: double.tryParse(priceCtrl.text) ?? 0.0,
                    discount: double.tryParse(discCtrl.text),
                    taxableAmount: double.tryParse(taxableCtrl.text),
                    gstRate: currentGstRate,
                    cgstAmount: double.tryParse(cgstCtrl.text),
                    sgstAmount: double.tryParse(sgstCtrl.text),
                    igstAmount: double.tryParse(igstCtrl.text),
                    cessAmount: double.tryParse(cessCtrl.text),
                    total: double.tryParse(totalCtrl.text),
                  );
                  widget.onUpdate(index, updatedItem);
                  Navigator.pop(dialogCtx);
                },
                icon: const Icon(Icons.check, size: 16),
                label: const Text('Apply Changes'),
              ),
            ],
          );
        },
      ),
    );
  }
}
