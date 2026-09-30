import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import '../config/theme.dart';
import '../models/invoice_models.dart';
import 'glass_card.dart';

const Map<String, String> _coaCodeToName = {
  'EXP-100': 'Operating Expense / Purchase',
  'EXP-PROF': 'Professional & Legal Charges',
  'EXP-SEC': 'Security Services',
  'EXP-TECH': 'Cloud Infrastructure & Hosting',
  'EXP-SOFT': 'Software & IT Subscriptions',
  'EXP-RENT': 'Rent & Occupancy Expenses',
  'EXP-ADJ': 'Additional Expense / Adjustment',
  'EXP-MISC': 'Miscellaneous Office Expense',
  'GST-CGST-IN': 'Input CGST Receivable',
  'GST-SGST-IN': 'Input SGST Receivable',
  'GST-IGST-IN': 'Input IGST Receivable',
  'TAX_BLOCKED': 'Input Tax Pending Verification',
  'TDS-PAY-200': 'TDS Payable',
  'AP-VEND-001': 'Accounts Payable - Vendor',
  'LIAB_AP': 'Accounts Payable',
  'LIAB_RCM_CGST': 'RCM CGST Payable (Recipient Liability)',
  'LIAB_RCM_SGST': 'RCM SGST / UTGST Payable (Recipient Liability)',
  'LIAB_RCM_IGST': 'RCM IGST Payable (Recipient Liability)',
};

const Map<String, String> _coaNameToCode = {
  'Operating Expense / Purchase': 'EXP-100',
  'Professional & Legal Charges': 'EXP-PROF',
  'Security Services': 'EXP-SEC',
  'Security & Facility Services': 'EXP-SEC',
  'Cloud Infrastructure & Hosting': 'EXP-TECH',
  'Software & IT Subscriptions': 'EXP-SOFT',
  'Rent & Occupancy Expenses': 'EXP-RENT',
  'Additional Expense / Adjustment': 'EXP-ADJ',
  'Miscellaneous Office Expense': 'EXP-MISC',
  'Input CGST Receivable': 'GST-CGST-IN',
  'Input SGST Receivable': 'GST-SGST-IN',
  'Input IGST Receivable': 'GST-IGST-IN',
  'Input Tax Pending Verification': 'TAX_BLOCKED',
  'TDS Payable': 'TDS-PAY-200',
  'Accounts Payable - Vendor': 'AP-VEND-001',
  'Accounts Payable': 'LIAB_AP',
  'RCM CGST Payable (Recipient Liability)': 'LIAB_RCM_CGST',
  'RCM SGST / UTGST Payable (Recipient Liability)': 'LIAB_RCM_SGST',
  'RCM IGST Payable (Recipient Liability)': 'LIAB_RCM_IGST',
};

class JournalPreviewWidget extends StatefulWidget {
  final JournalEntry? journal;
  final bool isCustomized;
  final void Function(int index, JournalLine line)? onLineChanged;
  final VoidCallback? onAddLine;
  final void Function(int index)? onDeleteLine;
  final VoidCallback? onResetToAuto;
  final VoidCallback? onExportZoho;
  final VoidCallback? onExportTally;

  const JournalPreviewWidget({
    super.key,
    required this.journal,
    this.isCustomized = false,
    this.onLineChanged,
    this.onAddLine,
    this.onDeleteLine,
    this.onResetToAuto,
    this.onExportZoho,
    this.onExportTally,
  });

  @override
  State<JournalPreviewWidget> createState() => _JournalPreviewWidgetState();
}

class _JournalPreviewWidgetState extends State<JournalPreviewWidget> {
  final ScrollController _horizontalScrollController = ScrollController();

  @override
  void dispose() {
    _horizontalScrollController.dispose();
    super.dispose();
  }

  void _handlePointerSignal(PointerSignalEvent event) {
    if (event is PointerScrollEvent && _horizontalScrollController.hasClients) {
      final maxExt = _horizontalScrollController.position.maxScrollExtent;
      if (maxExt <= 0) return;

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

  double _parseAmount(String val) {
    final cleaned = val.replaceAll(',', '').replaceAll('₹', '').replaceAll(' ', '').trim();
    return double.tryParse(cleaned) ?? 0.0;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final currencyFormat = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);
    final journal = widget.journal;

    if (journal == null || journal.lines.isEmpty) {
      return GlassCard(
        padding: const EdgeInsets.all(24),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.account_balance_outlined,
                size: 32,
                color: isDark ? AppTheme.darkTextMuted : AppTheme.lightTextMuted,
              ),
              const SizedBox(height: 8),
              Text(
                'No journal entries generated yet.',
                style: TextStyle(
                  fontSize: 13,
                  color: isDark ? AppTheme.darkTextSecondary : AppTheme.lightTextSecondary,
                ),
              ),
              if (widget.onAddLine != null) ...[
                const SizedBox(height: 12),
                ElevatedButton.icon(
                  onPressed: widget.onAddLine,
                  icon: const Icon(Icons.add_rounded, size: 16),
                  label: const Text('Add Journal Entry Line'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF5B5BF7),
                    foregroundColor: Colors.white,
                  ),
                ),
              ],
            ],
          ),
        ),
      );
    }

    final diff = (journal.totalDebit - journal.totalCredit).abs();
    final isBalanced = diff < 0.05;

    // Build standard list of codes and names
    final baseCodes = _coaCodeToName.keys.toList();
    final baseNames = _coaNameToCode.keys.toList();

    return GlassCard(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header with Title & Add/Reset Controls
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
                      color: const Color(0xFF5B5BF7).withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(
                      Icons.account_balance_rounded,
                      size: 18,
                      color: Color(0xFF5B5BF7),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Text(
                    'Authoritative Journal Entry (${journal.journalNumber ?? "Draft"})',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      color: isDark ? Colors.white : const Color(0xFF0F172A),
                    ),
                  ),
                ],
              ),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Directly Add Line into Table
                  if (widget.onAddLine != null)
                    ElevatedButton.icon(
                      onPressed: widget.onAddLine,
                      icon: const Icon(Icons.add_rounded, size: 16),
                      label: const Text('Add Line'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF5B5BF7),
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                        textStyle: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
                      ),
                    ),
                  if (widget.onResetToAuto != null) ...[
                    const SizedBox(width: 8),
                    OutlinedButton.icon(
                      onPressed: widget.onResetToAuto,
                      icon: const Icon(Icons.refresh_rounded, size: 15),
                      label: const Text('Reset Auto'),
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                        textStyle: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                      ),
                    ),
                  ],
                ],
              ),
            ],
          ),
          const SizedBox(height: 12),

          // Balance Status & Copy Icon
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: (isBalanced ? const Color(0xFF10B981) : const Color(0xFFEF4444)).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: isBalanced ? const Color(0xFF10B981) : const Color(0xFFEF4444),
                    width: 1,
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      isBalanced ? Icons.check_circle_rounded : Icons.warning_rounded,
                      size: 13,
                      color: isBalanced ? const Color(0xFF10B981) : const Color(0xFFEF4444),
                    ),
                    const SizedBox(width: 5),
                    Text(
                      isBalanced
                          ? '✓ Journal Balanced (Total Debit = Total Credit)'
                          : 'Imbalanced (Discrepancy: ${currencyFormat.format(diff)})',
                      style: TextStyle(
                        fontSize: 11.5,
                        fontWeight: FontWeight.w700,
                        color: isBalanced ? const Color(0xFF10B981) : const Color(0xFFEF4444),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              IconButton(
                icon: const Icon(Icons.copy_rounded, size: 17),
                tooltip: 'Copy Journal to Clipboard',
                onPressed: () {
                  final buffer = StringBuffer();
                  buffer.writeln('Account Code\tAccount Name\tDebit\tCredit');
                  for (final l in journal.lines) {
                    buffer.writeln('${l.accountCode}\t${l.accountName}\t${l.debit}\t${l.credit}');
                  }
                  Clipboard.setData(ClipboardData(text: buffer.toString()));
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('Journal entries copied to clipboard'),
                      duration: Duration(seconds: 2),
                    ),
                  );
                },
              ),
            ],
          ),
          const SizedBox(height: 14),

          // Direct Inline Editable Journal Table with Dropdowns
          Listener(
            onPointerSignal: _handlePointerSignal,
            child: Scrollbar(
              controller: _horizontalScrollController,
              thumbVisibility: true,
              trackVisibility: true,
              thickness: 8,
              radius: const Radius.circular(4),
              child: SingleChildScrollView(
                controller: _horizontalScrollController,
                scrollDirection: Axis.horizontal,
                physics: const BouncingScrollPhysics(parent: AlwaysScrollableScrollPhysics()),
                padding: const EdgeInsets.only(bottom: 10),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(minWidth: 780),
                  child: DataTable(
                    headingRowColor: WidgetStateProperty.all(
                      isDark ? const Color(0xFF0F172A) : const Color(0xFFF1F5F9),
                    ),
                    horizontalMargin: 12,
                    columnSpacing: 14,
                    dataRowMinHeight: 48,
                    dataRowMaxHeight: 56,
                    columns: const [
                      DataColumn(label: Text('Type', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12.5))),
                      DataColumn(label: Text('Account Code', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12.5))),
                      DataColumn(label: Text('Account Name', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12.5))),
                      DataColumn(label: Text('Debit (₹)', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12.5))),
                      DataColumn(label: Text('Credit (₹)', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12.5))),
                      DataColumn(label: Text('Action', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12.5))),
                    ],
                    rows: [
                      ...journal.lines.asMap().entries.map((entry) {
                        final index = entry.key;
                        final line = entry.value;
                        final isDebit = line.debit > 0;

                        // Dynamic code list including current code
                        final availableCodes = baseCodes.contains(line.accountCode)
                            ? baseCodes
                            : [line.accountCode, ...baseCodes];

                        // Dynamic name list including current name
                        final availableNames = baseNames.contains(line.accountName)
                            ? baseNames
                            : [line.accountName, ...baseNames];

                        return DataRow(
                          key: ValueKey('journal_row_${index}_${line.accountCode}_${line.accountName}_${line.debit}_${line.credit}'),
                          cells: [
                            // DR / CR Toggle Pill
                            DataCell(
                              InkWell(
                                onTap: widget.onLineChanged != null
                                    ? () {
                                        if (isDebit) {
                                          line.credit = line.debit;
                                          line.debit = 0.0;
                                        } else {
                                          line.debit = line.credit;
                                          line.credit = 0.0;
                                        }
                                        widget.onLineChanged!(index, line);
                                      }
                                    : null,
                                borderRadius: BorderRadius.circular(6),
                                child: Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                                  decoration: BoxDecoration(
                                    color: (isDebit ? const Color(0xFF10B981) : const Color(0xFF3B82F6)).withValues(alpha: 0.15),
                                    borderRadius: BorderRadius.circular(6),
                                  ),
                                  child: Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Text(
                                        isDebit ? 'DR' : 'CR',
                                        style: TextStyle(
                                          fontSize: 11,
                                          fontWeight: FontWeight.w800,
                                          color: isDebit ? const Color(0xFF10B981) : const Color(0xFF3B82F6),
                                        ),
                                      ),
                                      const SizedBox(width: 3),
                                      Icon(
                                        Icons.swap_vert_rounded,
                                        size: 12,
                                        color: isDebit ? const Color(0xFF10B981) : const Color(0xFF3B82F6),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ),

                            // Account Code Dropdown
                            DataCell(
                              SizedBox(
                                width: 155,
                                child: DropdownButtonHideUnderline(
                                  child: DropdownButton<String>(
                                    value: availableCodes.contains(line.accountCode) ? line.accountCode : availableCodes.first,
                                    isExpanded: true,
                                    isDense: true,
                                    icon: const Icon(Icons.arrow_drop_down_rounded, size: 18),
                                    style: TextStyle(
                                      fontSize: 12,
                                      fontFamily: 'monospace',
                                      fontWeight: FontWeight.w600,
                                      color: isDark ? Colors.white : const Color(0xFF0F172A),
                                    ),
                                    dropdownColor: isDark ? const Color(0xFF1E293B) : Colors.white,
                                    items: availableCodes.map((code) {
                                      return DropdownMenuItem<String>(
                                        value: code,
                                        child: Text(code, overflow: TextOverflow.ellipsis),
                                      );
                                    }).toList(),
                                    onChanged: (val) {
                                      if (val != null) {
                                        line.accountCode = val;
                                        if (_coaCodeToName.containsKey(val)) {
                                          line.accountName = _coaCodeToName[val]!;
                                        }
                                        widget.onLineChanged?.call(index, line);
                                      }
                                    },
                                  ),
                                ),
                              ),
                            ),

                            // Account Name Dropdown
                            DataCell(
                              SizedBox(
                                width: 245,
                                child: DropdownButtonHideUnderline(
                                  child: DropdownButton<String>(
                                    value: availableNames.contains(line.accountName) ? line.accountName : availableNames.first,
                                    isExpanded: true,
                                    isDense: true,
                                    icon: const Icon(Icons.arrow_drop_down_rounded, size: 18),
                                    style: TextStyle(
                                      fontSize: 12.5,
                                      fontWeight: FontWeight.w500,
                                      color: isDark ? Colors.white : const Color(0xFF0F172A),
                                    ),
                                    dropdownColor: isDark ? const Color(0xFF1E293B) : Colors.white,
                                    items: availableNames.map((name) {
                                      return DropdownMenuItem<String>(
                                        value: name,
                                        child: Text(name, overflow: TextOverflow.ellipsis),
                                      );
                                    }).toList(),
                                    onChanged: (val) {
                                      if (val != null) {
                                        line.accountName = val;
                                        if (_coaNameToCode.containsKey(val)) {
                                          line.accountCode = _coaNameToCode[val]!;
                                        }
                                        widget.onLineChanged?.call(index, line);
                                      }
                                    },
                                  ),
                                ),
                              ),
                            ),

                            // Debit (₹) Inline Text Input (Clean & Normal)
                            DataCell(
                              SizedBox(
                                width: 110,
                                child: TextFormField(
                                  key: ValueKey('debit_${index}_${line.debit}'),
                                  initialValue: line.debit > 0 ? line.debit.toStringAsFixed(2) : '',
                                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                                  textAlign: TextAlign.right,
                                  style: TextStyle(
                                    fontSize: 12.5,
                                    fontWeight: line.debit > 0 ? FontWeight.w700 : FontWeight.normal,
                                    color: line.debit > 0 ? (isDark ? Colors.white : const Color(0xFF0F172A)) : null,
                                  ),
                                  decoration: const InputDecoration(
                                    hintText: '-',
                                    isDense: true,
                                    contentPadding: EdgeInsets.symmetric(horizontal: 6, vertical: 8),
                                    border: InputBorder.none,
                                    focusedBorder: UnderlineInputBorder(
                                      borderSide: BorderSide(color: Color(0xFF6366F1), width: 1.5),
                                    ),
                                  ),
                                  onChanged: (val) {
                                    final amt = _parseAmount(val);
                                    line.debit = amt;
                                    if (amt > 0) {
                                      line.credit = 0.0;
                                    }
                                    widget.onLineChanged?.call(index, line);
                                  },
                                ),
                              ),
                            ),

                            // Credit (₹) Inline Text Input (Clean & Normal)
                            DataCell(
                              SizedBox(
                                width: 110,
                                child: TextFormField(
                                  key: ValueKey('credit_${index}_${line.credit}'),
                                  initialValue: line.credit > 0 ? line.credit.toStringAsFixed(2) : '',
                                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                                  textAlign: TextAlign.right,
                                  style: TextStyle(
                                    fontSize: 12.5,
                                    fontWeight: line.credit > 0 ? FontWeight.w700 : FontWeight.normal,
                                    color: line.credit > 0 ? (isDark ? Colors.white : const Color(0xFF0F172A)) : null,
                                  ),
                                  decoration: const InputDecoration(
                                    hintText: '-',
                                    isDense: true,
                                    contentPadding: EdgeInsets.symmetric(horizontal: 6, vertical: 8),
                                    border: InputBorder.none,
                                    focusedBorder: UnderlineInputBorder(
                                      borderSide: BorderSide(color: Color(0xFF6366F1), width: 1.5),
                                    ),
                                  ),
                                  onChanged: (val) {
                                    final amt = _parseAmount(val);
                                    line.credit = amt;
                                    if (amt > 0) {
                                      line.debit = 0.0;
                                    }
                                    widget.onLineChanged?.call(index, line);
                                  },
                                ),
                              ),
                            ),

                            // Delete Action
                            DataCell(
                              widget.onDeleteLine != null
                                  ? IconButton(
                                      icon: const Icon(Icons.delete_outline_rounded, size: 17, color: Color(0xFFEF4444)),
                                      tooltip: 'Delete line',
                                      onPressed: () => widget.onDeleteLine!(index),
                                    )
                                  : const SizedBox.shrink(),
                            ),
                          ],
                        );
                      }),

                      // Total Summary Row
                      DataRow(
                        color: WidgetStateProperty.all(
                          isDark ? const Color(0xFF0F172A).withValues(alpha: 0.8) : const Color(0xFFF1F5F9),
                        ),
                        cells: [
                          const DataCell(Text('')),
                          const DataCell(
                            Text('TOTAL', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 12)),
                          ),
                          const DataCell(Text('')),
                          DataCell(
                            Align(
                              alignment: Alignment.centerRight,
                              child: Text(
                                currencyFormat.format(journal.totalDebit),
                                style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 13, color: Color(0xFF5B5BF7)),
                              ),
                            ),
                          ),
                          DataCell(
                            Align(
                              alignment: Alignment.centerRight,
                              child: Text(
                                currencyFormat.format(journal.totalCredit),
                                style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 13, color: Color(0xFF5B5BF7)),
                              ),
                            ),
                          ),
                          const DataCell(Text('')),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),

          const SizedBox(height: 16),

          // Quick ERP Action Buttons
          Wrap(
            spacing: 12,
            runSpacing: 8,
            children: [
              if (widget.onExportZoho != null)
                ElevatedButton.icon(
                  onPressed: isBalanced ? widget.onExportZoho : null,
                  icon: const Icon(Icons.cloud_upload_rounded, size: 16),
                  label: const Text('Post Bill to Zoho Books'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF5B5BF7),
                    foregroundColor: Colors.white,
                    disabledBackgroundColor: const Color(0xFF5B5BF7).withValues(alpha: 0.4),
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    textStyle: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
                  ),
                ),
              if (widget.onExportTally != null)
                OutlinedButton.icon(
                  onPressed: isBalanced ? widget.onExportTally : null,
                  icon: const Icon(Icons.download_rounded, size: 16),
                  label: const Text('Download Tally XML Voucher'),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    textStyle: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}
