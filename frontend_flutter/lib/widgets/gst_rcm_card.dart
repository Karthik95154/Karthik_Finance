import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../models/invoice_models.dart';
import '../providers/invoice_provider.dart';
import 'financial_confirmation_dialog.dart';
import 'glass_card.dart';

class GstRcmCard extends StatefulWidget {
  final GstResult? gstResult;
  final ExtractedInvoiceData? extractedData;
  final bool isRcmActive;

  const GstRcmCard({
    super.key,
    this.gstResult,
    this.extractedData,
    this.isRcmActive = false,
  });

  @override
  State<GstRcmCard> createState() => _GstRcmCardState();
}

class _GstRcmCardState extends State<GstRcmCard> {
  bool _isEditingDetails = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final provider = context.watch<InvoiceProvider>();
    final currency = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);

    final extData = provider.editableData ?? widget.extractedData;
    final isRcm = provider.editableTds?.isRcm ?? (widget.gstResult?.isReverseCharge == true);

    final cgst = extData?.cgstAmount ?? 0.0;
    final sgst = extData?.sgstAmount ?? 0.0;
    final igst = extData?.igstAmount ?? 0.0;
    final cess = extData?.cessAmount ?? 0.0;
    final taxable = extData?.taxableAmount ?? 0.0;

    final supplyType = widget.gstResult?.supplyType ??
        (igst > 0 ? 'INTER_STATE' : 'INTRA_STATE');
    final isInterState = supplyType == 'INTER_STATE' || igst > 0;
    final hasMismatch = widget.gstResult?.validationStatus == 'GST_MISMATCH';
    final componentTax = cgst + sgst + igst + cess;
    final totalTax = componentTax > 0 ? componentTax : (extData?.taxTotal ?? 0.0);
    final grandTotal = taxable + totalTax;
    final tdsAmount = provider.editableTds?.tdsAmount ?? (provider.editableTds?.applicable == true ? taxable * ((provider.editableTds?.tdsRate ?? 10.0) / 100) : 0.0);
    final vendorPayable = (isRcm ? taxable : grandTotal) - tdsAmount;

    return GlassCard(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header Row
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.blue.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(Icons.receipt_long_outlined, color: Colors.blue, size: 20),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'GST & Supply Engine',
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                          letterSpacing: 0.2,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        'Statutory tax regime, place of supply & reverse charge determination',
                        style: TextStyle(
                          fontSize: 11,
                          color: theme.textTheme.bodySmall?.color?.withValues(alpha: 0.75),
                        ),
                      ),
                    ],
                  ),
                ),
                // Edit GST Values Button
                IconButton(
                  tooltip: _isEditingDetails ? 'Hide Quick Editor' : 'Edit GST Tax Figures',
                  icon: Icon(_isEditingDetails ? Icons.expand_less : Icons.tune_rounded, size: 20, color: Colors.blueAccent),
                  onPressed: () {
                    setState(() => _isEditingDetails = !_isEditingDetails);
                  },
                ),
                const SizedBox(width: 8),
                // RCM Toggle Switch
                Row(
                  children: [
                    Text(
                      isRcm ? 'RCM Active' : 'Forward Charge',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: isRcm ? Colors.deepOrangeAccent : Colors.grey,
                      ),
                    ),
                    const SizedBox(width: 6),
                    Switch.adaptive(
                      value: isRcm,
                      activeColor: Colors.deepOrangeAccent,
                      onChanged: (val) {
                        provider.updateTds(isRcm: val);
                      },
                    ),
                  ],
                ),
              ],
            ),

            const SizedBox(height: 14),

            // Dedicated Place of Supply & Supply Regime Statutory Bar
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: isDark ? const Color(0xFF0F172A) : const Color(0xFFF1F5F9),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                  color: isDark ? const Color(0xFF334155) : const Color(0xFFCBD5E1),
                ),
              ),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(7),
                    decoration: BoxDecoration(
                      color: const Color(0xFF0284C7).withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(Icons.location_on_rounded, color: Color(0xFF0284C7), size: 18),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Text(
                              'Place of Supply (POS): ',
                              style: TextStyle(
                                fontSize: 11.5,
                                fontWeight: FontWeight.w600,
                                color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B),
                              ),
                            ),
                            InkWell(
                              onTap: () => _showEditPosDialog(context, extData?.placeOfSupply, provider),
                              borderRadius: BorderRadius.circular(4),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Text(
                                    extData?.placeOfSupply ?? "Automated GSTIN Resolution",
                                    style: const TextStyle(
                                      fontSize: 13,
                                      fontWeight: FontWeight.bold,
                                      color: Color(0xFF0284C7),
                                      decoration: TextDecoration.underline,
                                    ),
                                  ),
                                  const SizedBox(width: 4),
                                  const Icon(Icons.edit_note_rounded, size: 16, color: Color(0xFF0284C7)),
                                ],
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 2),
                        Text(
                          isInterState
                              ? 'Inter-State Supply (IGST Applicable across state borders)'
                              : 'Intra-State Supply (50% CGST + 50% SGST Applicable for local supply)',
                          style: TextStyle(
                            fontSize: 10.5,
                            color: isDark ? const Color(0xFF64748B) : const Color(0xFF94A3B8),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  // Clickable Supply Type Pill
                  InkWell(
                    onTap: () async {
                      final willBeInterState = !isInterState;
                      final curTotalTax = widget.extractedData?.taxTotal ?? 0.0;
                      final currencyFmt = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);
                      final confirmed = await showFinancialConfirmationDialog(
                        context: context,
                        actionTitle: willBeInterState ? 'Switch to Inter-State (IGST)' : 'Switch to Intra-State (CGST + SGST)',
                        reason: willBeInterState
                            ? 'Convert tax schedule to Integrated GST (IGST) for interstate transactions.'
                            : 'Split tax equally into Central GST (CGST) and State GST (SGST) for local supply.',
                        formulaExplanation: willBeInterState ? 'IGST = 100% of GST rate' : 'CGST = 50% of GST rate, SGST = 50% of GST rate',
                        comparisons: [
                          FinancialFieldComparison(
                            label: 'Supply Regime',
                            currentValue: isInterState ? 'Inter-State (IGST)' : 'Intra-State (CGST+SGST)',
                            proposedValue: willBeInterState ? 'Inter-State (IGST)' : 'Intra-State (CGST+SGST)',
                            difference: 'Regime Switch',
                            isDifferent: true,
                          ),
                          FinancialFieldComparison(
                            label: 'Total GST Amount',
                            currentValue: currencyFmt.format(curTotalTax),
                            proposedValue: currencyFmt.format(curTotalTax),
                            difference: '₹0.00 (Unchanged)',
                            isDifferent: false,
                          ),
                        ],
                      );

                      if (confirmed && context.mounted) {
                        provider.applyConfirmedTaxSupplySwitch(targetInterState: willBeInterState);
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text('Tax supply switched to ${willBeInterState ? "IGST" : "CGST+SGST"} after user confirmation.'),
                            backgroundColor: const Color(0xFF0284C7),
                            behavior: SnackBarBehavior.floating,
                          ),
                        );
                      }
                    },
                    borderRadius: BorderRadius.circular(8),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      decoration: BoxDecoration(
                        color: (isInterState ? Colors.purple : Colors.teal).withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: (isInterState ? Colors.purple : Colors.teal).withValues(alpha: 0.4),
                        ),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            isInterState ? 'INTER-STATE (IGST)' : 'INTRA-STATE (CGST+SGST)',
                            style: theme.textTheme.labelSmall?.copyWith(
                              color: isInterState ? Colors.purpleAccent : Colors.teal,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(width: 4),
                          const Icon(Icons.swap_horiz, size: 14, color: Colors.grey),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),

            if (hasMismatch) ...[
              const SizedBox(height: 14),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.amber.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.amber.withOpacity(0.4)),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.warning_amber_rounded, color: Colors.amber, size: 20),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'GST Mismatch Detected: Extracted invoice tax totals differ from statutory mathematical calculation.',
                        style: TextStyle(fontSize: 12, color: Colors.amber.shade200),
                      ),
                    ),
                  ],
                ),
              ),
            ],

            // In-place Quick GST Figures Editor (when expanded)
            if (_isEditingDetails) ...[
              const SizedBox(height: 14),
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: theme.colorScheme.surfaceContainerHighest.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.blueAccent.withOpacity(0.3)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Edit GST Statutory Breakdown (₹)', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.blueAccent)),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Expanded(
                          child: TextFormField(
                            key: ValueKey('gst_cgst_$cgst'),
                            initialValue: cgst.toStringAsFixed(2),
                            keyboardType: const TextInputType.numberWithOptions(decimal: true),
                            decoration: const InputDecoration(labelText: 'CGST (₹)', border: OutlineInputBorder(), isDense: true),
                            onChanged: (v) {
                              final val = double.tryParse(v) ?? 0.0;
                              extData?.cgstAmount = val;
                              extData?.taxTotal = val + (extData?.sgstAmount ?? 0.0) + (extData?.igstAmount ?? 0.0) + (extData?.cessAmount ?? 0.0);
                              provider.updateFinancialSummary(cgstAmount: val, taxTotal: extData?.taxTotal);
                            },
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: TextFormField(
                            key: ValueKey('gst_sgst_$sgst'),
                            initialValue: sgst.toStringAsFixed(2),
                            keyboardType: const TextInputType.numberWithOptions(decimal: true),
                            decoration: const InputDecoration(labelText: 'SGST (₹)', border: OutlineInputBorder(), isDense: true),
                            onChanged: (v) {
                              final val = double.tryParse(v) ?? 0.0;
                              extData?.sgstAmount = val;
                              extData?.taxTotal = (extData?.cgstAmount ?? 0.0) + val + (extData?.igstAmount ?? 0.0) + (extData?.cessAmount ?? 0.0);
                              provider.updateFinancialSummary(sgstAmount: val, taxTotal: extData?.taxTotal);
                            },
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: TextFormField(
                            key: ValueKey('gst_igst_$igst'),
                            initialValue: igst.toStringAsFixed(2),
                            keyboardType: const TextInputType.numberWithOptions(decimal: true),
                            decoration: const InputDecoration(labelText: 'IGST (₹)', border: OutlineInputBorder(), isDense: true),
                            onChanged: (v) {
                              final val = double.tryParse(v) ?? 0.0;
                              extData?.igstAmount = val;
                              extData?.taxTotal = (extData?.cgstAmount ?? 0.0) + (extData?.sgstAmount ?? 0.0) + val + (extData?.cessAmount ?? 0.0);
                              provider.updateFinancialSummary(igstAmount: val, taxTotal: extData?.taxTotal);
                            },
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: TextFormField(
                            key: ValueKey('gst_cess_$cess'),
                            initialValue: cess.toStringAsFixed(2),
                            keyboardType: const TextInputType.numberWithOptions(decimal: true),
                            decoration: const InputDecoration(labelText: 'CESS (₹)', border: OutlineInputBorder(), isDense: true),
                            onChanged: (v) {
                              final val = double.tryParse(v) ?? 0.0;
                              extData?.cessAmount = val;
                              extData?.taxTotal = (extData?.cgstAmount ?? 0.0) + (extData?.sgstAmount ?? 0.0) + (extData?.igstAmount ?? 0.0) + val;
                              provider.updateFinancialSummary(cessAmount: val, taxTotal: extData?.taxTotal);
                            },
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],

            const SizedBox(height: 16),
            const Divider(height: 1),
            const SizedBox(height: 16),

            // Separate GST Breakdown (CGST, SGST, IGST, Total Tax & Vendor Payable)
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: isRcm ? Colors.deepOrangeAccent.withOpacity(0.08) : theme.colorScheme.surfaceContainerHighest.withOpacity(0.3),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                  color: isRcm ? Colors.deepOrangeAccent.withOpacity(0.35) : theme.dividerColor.withOpacity(0.4),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  LayoutBuilder(
                    builder: (context, constraints) {
                      final isNarrow = constraints.maxWidth < 650;
                      if (isNarrow) {
                        return Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            _buildStatBox(context, 'Taxable Base', currency.format(taxable), 'Pre-tax base', Icons.account_balance_wallet_outlined),
                            if (!isInterState || cgst > 0)
                              _buildStatBox(context, 'CGST', currency.format(cgst), 'Central Tax', Icons.domain, color: Colors.tealAccent.shade400),
                            if (!isInterState || sgst > 0)
                              _buildStatBox(context, 'SGST / UTGST', currency.format(sgst), 'State Tax', Icons.location_city, color: Colors.tealAccent.shade400),
                            if (isInterState || igst > 0)
                              _buildStatBox(context, 'IGST', currency.format(igst), 'Integrated Tax', Icons.public, color: Colors.purpleAccent),
                            if (cess > 0)
                              _buildStatBox(context, 'CESS', currency.format(cess), 'Comp. Cess', Icons.savings_outlined, color: Colors.amberAccent),
                            _buildStatBox(context, 'Total GST Tax', currency.format(totalTax), isInterState ? 'IGST Total' : 'CGST + SGST', Icons.receipt_long, color: Colors.blueAccent),
                            _buildStatBox(
                              context,
                              'Net Vendor Payable',
                              currency.format(vendorPayable),
                              isRcm ? 'Excl. Tax (RCM)' : 'Incl. Full Tax',
                              Icons.payments_outlined,
                              isHighlight: true,
                              color: isRcm ? Colors.deepOrangeAccent : const Color(0xFF10B981),
                            ),
                          ],
                        );
                      }
                      return Row(
                        children: [
                          Expanded(
                            child: _buildStatBox(context, 'Taxable Base', currency.format(taxable), 'Pre-tax base', Icons.account_balance_wallet_outlined),
                          ),
                          const SizedBox(width: 8),
                          if (!isInterState || cgst > 0) ...[
                            Expanded(
                              child: _buildStatBox(context, 'CGST', currency.format(cgst), 'Central Tax', Icons.domain, color: Colors.tealAccent.shade400),
                            ),
                            const SizedBox(width: 8),
                          ],
                          if (!isInterState || sgst > 0) ...[
                            Expanded(
                              child: _buildStatBox(context, 'SGST / UTGST', currency.format(sgst), 'State Tax', Icons.location_city, color: Colors.tealAccent.shade400),
                            ),
                            const SizedBox(width: 8),
                          ],
                          if (isInterState || igst > 0) ...[
                            Expanded(
                              child: _buildStatBox(context, 'IGST', currency.format(igst), 'Integrated Tax', Icons.public, color: Colors.purpleAccent),
                            ),
                            const SizedBox(width: 8),
                          ],
                          if (cess > 0) ...[
                            Expanded(
                              child: _buildStatBox(context, 'CESS', currency.format(cess), 'Comp. Cess', Icons.savings_outlined, color: Colors.amberAccent),
                            ),
                            const SizedBox(width: 8),
                          ],
                          Expanded(
                            child: _buildStatBox(context, 'Total GST Tax', currency.format(totalTax), isInterState ? 'IGST Total' : 'CGST + SGST', Icons.receipt_long, color: Colors.blueAccent),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: _buildStatBox(
                              context,
                              'Net Vendor Payable',
                              currency.format(vendorPayable),
                              isRcm ? 'Excl. Tax (RCM)' : 'Incl. Full Tax',
                              Icons.payments_outlined,
                              isHighlight: true,
                              color: isRcm ? Colors.deepOrangeAccent : const Color(0xFF10B981),
                            ),
                          ),
                        ],
                      );
                    },
                  ),
                  if (isRcm) ...[
                    const SizedBox(height: 10),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      decoration: BoxDecoration(
                        color: Colors.deepOrangeAccent.withOpacity(0.12),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.info_outline, size: 14, color: Colors.deepOrangeAccent),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Text(
                              'Under Reverse Charge Mechanism (RCM), buyer pays GST of ${currency.format(totalTax)} (${isInterState ? "IGST: " + currency.format(igst) : "CGST: " + currency.format(cgst) + " + SGST: " + currency.format(sgst)}) directly to the Government. Vendor is only paid base subtotal.',
                              style: const TextStyle(fontSize: 11, color: Colors.deepOrangeAccent, fontWeight: FontWeight.w500),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _showEditPosDialog(BuildContext context, String? currentPos, InvoiceProvider provider) {
    final ctrl = TextEditingController(text: currentPos ?? '');
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Edit Place of Supply (POS)'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Enter state name or 2-digit GST state code (e.g. "36 - Telangana" or "27 - Maharashtra"):', style: TextStyle(fontSize: 12)),
            const SizedBox(height: 12),
            TextField(
              controller: ctrl,
              decoration: const InputDecoration(labelText: 'Place of Supply', border: OutlineInputBorder()),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () {
              provider.updateGst(placeOfSupply: ctrl.text.trim());
              Navigator.pop(ctx);
            },
            child: const Text('Save POS'),
          ),
        ],
      ),
    );
  }

  Widget _buildStatBox(
    BuildContext context,
    String label,
    String value,
    String subtitle,
    IconData icon, {
    Color? color,
    bool isHighlight = false,
  }) {
    final theme = Theme.of(context);
    final accentColor = color ?? theme.textTheme.bodyMedium?.color;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: isHighlight ? accentColor?.withOpacity(0.1) : theme.colorScheme.surfaceContainerHighest.withOpacity(0.2),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: isHighlight ? accentColor?.withOpacity(0.4) ?? theme.dividerColor : theme.dividerColor.withOpacity(0.3),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Icon(icon, size: 12, color: accentColor),
              const SizedBox(width: 4),
              Expanded(
                child: Text(
                  label,
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                    color: theme.textTheme.bodySmall?.color,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: TextStyle(
              fontSize: isHighlight ? 14 : 12,
              fontWeight: FontWeight.bold,
              color: isHighlight ? accentColor : theme.textTheme.bodyLarge?.color,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            subtitle,
            style: TextStyle(
              fontSize: 9,
              color: theme.textTheme.bodySmall?.color?.withOpacity(0.7),
            ),
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}
