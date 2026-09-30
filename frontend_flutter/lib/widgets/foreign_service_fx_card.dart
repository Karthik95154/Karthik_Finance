import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../config/theme.dart';
import '../models/invoice_models.dart';
import '../providers/invoice_provider.dart';
import 'glass_card.dart';

class ForeignServiceFxCard extends StatefulWidget {
  final Invoice invoice;

  const ForeignServiceFxCard({super.key, required this.invoice});

  @override
  State<ForeignServiceFxCard> createState() => _ForeignServiceFxCardState();
}

class _ForeignServiceFxCardState extends State<ForeignServiceFxCard> {
  void _showClassificationOverrideDialog(BuildContext context) {
    final invProv = Provider.of<InvoiceProvider>(context, listen: false);
    String selectedClass = widget.invoice.invoiceOrigin ?? 'FOREIGN_SERVICE';
    final reasonController = TextEditingController();
    final formKey = GlobalKey<FormState>();

    showDialog(
      context: context,
      builder: (dialogCtx) => StatefulBuilder(
        builder: (context, setDialogState) {
          final isDark = Theme.of(context).brightness == Brightness.dark;
          return AlertDialog(
            backgroundColor: isDark ? const Color(0xFF0F172A) : Colors.white,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            title: Row(
              children: [
                const Icon(Icons.swap_horiz_rounded, color: Color(0xFF38BDF8), size: 24),
                const SizedBox(width: 8),
                const Text('Override Invoice Classification', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              ],
            ),
            content: SizedBox(
              width: 480,
              child: Form(
                key: formKey,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Select the authoritative classification. An explicit audit reason is mandatory.',
                      style: TextStyle(fontSize: 12, color: Color(0xFF94A3B8)),
                    ),
                    const SizedBox(height: 16),
                    DropdownButtonFormField<String>(
                      value: selectedClass,
                      decoration: InputDecoration(
                        labelText: 'Authoritative Classification',
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                        filled: true,
                        fillColor: isDark ? const Color(0xFF1E293B) : const Color(0xFFF8FAFC),
                      ),
                      items: const [
                        DropdownMenuItem(value: 'FOREIGN_SERVICE', child: Text('FOREIGN_SERVICE — Import of Foreign Services')),
                        DropdownMenuItem(value: 'INDIAN', child: Text('INDIAN — Domestic Indian Supplier')),
                        DropdownMenuItem(value: 'REVIEW_REQUIRED', child: Text('REVIEW_REQUIRED — Needs Clarification')),
                        DropdownMenuItem(value: 'UNSUPPORTED_FOREIGN_GOODS', child: Text('UNSUPPORTED_FOREIGN_GOODS — Physical Goods')),
                      ],
                      onChanged: (val) {
                        if (val != null) setDialogState(() => selectedClass = val);
                      },
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: reasonController,
                      maxLines: 3,
                      decoration: InputDecoration(
                        labelText: 'Reason for Override *',
                        hintText: 'e.g., Overseas vendor confirmed as SaaS provider with no Indian establishment.',
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                        filled: true,
                        fillColor: isDark ? const Color(0xFF1E293B) : const Color(0xFFF8FAFC),
                      ),
                      validator: (val) {
                        if (val == null || val.trim().isEmpty) {
                          return 'Please provide an explicit audit reason.';
                        }
                        return null;
                      },
                    ),
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(dialogCtx).pop(),
                child: const Text('Cancel'),
              ),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF0284C7),
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                onPressed: () async {
                  if (formKey.currentState?.validate() ?? false) {
                    Navigator.of(dialogCtx).pop();
                    final success = await invProv.overrideClassification(
                      widget.invoice.id,
                      selectedClass,
                      reasonController.text.trim(),
                    );
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text(success ? 'Classification updated successfully.' : 'Failed to update classification.'),
                          backgroundColor: success ? const Color(0xFF10B981) : const Color(0xFFEF4444),
                        ),
                      );
                    }
                  }
                },
                child: const Text('Confirm Override'),
              ),
            ],
          );
        },
      ),
    );
  }

  void _showFxOverrideDialog(BuildContext context) {
    final invProv = Provider.of<InvoiceProvider>(context, listen: false);
    final currentRate = widget.invoice.exchangeRate ?? 1.0;
    final rateController = TextEditingController(text: currentRate.toStringAsFixed(6));
    final reasonController = TextEditingController();
    final formKey = GlobalKey<FormState>();

    showDialog(
      context: context,
      builder: (dialogCtx) => StatefulBuilder(
        builder: (context, setDialogState) {
          final isDark = Theme.of(context).brightness == Brightness.dark;
          return AlertDialog(
            backgroundColor: isDark ? const Color(0xFF0F172A) : Colors.white,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            title: Row(
              children: [
                const Icon(Icons.currency_exchange_rounded, color: Color(0xFFF59E0B), size: 24),
                const SizedBox(width: 8),
                const Text('Finance FX Rate Override', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              ],
            ),
            content: SizedBox(
              width: 480,
              child: Form(
                key: formKey,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Enter custom exchange rate for INR conversion (e.g. from RBI / FBIL portal). System rate is preserved in audit trail.',
                      style: TextStyle(fontSize: 12, color: Color(0xFF94A3B8)),
                    ),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 8,
                      runSpacing: 6,
                      children: [
                        ActionChip(
                          avatar: const Icon(Icons.account_balance_rounded, size: 14, color: Color(0xFF10B981)),
                          label: const Text('RBI / FBIL Rate (95.2408)', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
                          onPressed: () {
                            setDialogState(() {
                              rateController.text = '95.2408';
                              reasonController.text = 'RBI Reference Rate (₹95.2408 / USD) from official RBI portal for invoice date (${widget.invoice.extractedData?.invoiceDate ?? '2026-07-04'}).';
                            });
                          },
                        ),
                        ActionChip(
                          avatar: const Icon(Icons.gavel_rounded, size: 14, color: Color(0xFF0284C7)),
                          label: const Text('Rule 115 SBI TTBR', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
                          onPressed: () {
                            setDialogState(() {
                              reasonController.text = 'SBI TT Buying Rate as per Rule 115 of Income-tax Rules on invoice date.';
                            });
                          },
                        ),
                        ActionChip(
                          avatar: const Icon(Icons.payment_rounded, size: 14, color: Color(0xFFF59E0B)),
                          label: const Text('Bank Remittance Rate', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
                          onPressed: () {
                            setDialogState(() {
                              reasonController.text = 'Bank Forex remittance contract / TT card rate on invoice settlement date.';
                            });
                          },
                        ),
                      ],
                    ),
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: rateController,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      decoration: InputDecoration(
                        labelText: 'FX Exchange Rate (1 ${widget.invoice.originalCurrency ?? widget.invoice.currency ?? 'USD'} = ? INR) *',
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                        filled: true,
                        fillColor: isDark ? const Color(0xFF1E293B) : const Color(0xFFF8FAFC),
                      ),
                      validator: (val) {
                        if (val == null || val.trim().isEmpty) return 'Rate is required.';
                        final num = double.tryParse(val.trim());
                        if (num == null || num <= 0) return 'Must be a positive number.';
                        return null;
                      },
                    ),
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: reasonController,
                      maxLines: 2,
                      decoration: InputDecoration(
                        labelText: 'Reason for FX Override *',
                        hintText: 'e.g., RBI / FBIL Reference Rate from official portal on invoice date.',
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                        filled: true,
                        fillColor: isDark ? const Color(0xFF1E293B) : const Color(0xFFF8FAFC),
                      ),
                      validator: (val) {
                        if (val == null || val.trim().isEmpty) {
                          return 'Please provide an explicit audit reason.';
                        }
                        return null;
                      },
                    ),
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(dialogCtx).pop(),
                child: const Text('Cancel'),
              ),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFFF59E0B),
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                onPressed: () async {
                  if (formKey.currentState?.validate() ?? false) {
                    final newRate = double.parse(rateController.text.trim());
                    Navigator.of(dialogCtx).pop();
                    final success = await invProv.overrideExchangeRate(
                      widget.invoice.id,
                      newRate,
                      reasonController.text.trim(),
                    );
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text(success ? 'FX rate overridden. Downstream taxes recalculated.' : 'Failed to override FX rate.'),
                          backgroundColor: success ? const Color(0xFF10B981) : const Color(0xFFEF4444),
                        ),
                      );
                    }
                  }
                },
                child: const Text('Apply & Recalculate'),
              ),
            ],
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final inrFormat = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);
    final inv = widget.invoice;
    final ext = inv.extractedData;

    final origCurr = inv.originalCurrency ?? ext?.currency ?? inv.currency ?? 'USD';
    final origTotal = inv.originalTotalAmount ?? ext?.originalTotalAmount ?? ext?.totalAmount ?? 0.0;
    final origTaxable = inv.originalTaxableAmount ?? ext?.originalTaxableAmount ?? ext?.taxableAmount ?? origTotal;

    final rate = inv.exchangeRate ?? 1.0;
    final fxSource = inv.exchangeRateSource ?? 'EXCHANGE_RATE_API';
    final fxDate = inv.exchangeRateDate ?? ext?.invoiceDate ?? 'Latest';
    final isOverridden = inv.fxRateOverridden == true;
    final origSysRate = inv.fxOriginalRate ?? rate;
    final isFallback = fxSource.contains('FALLBACK') || fxSource.contains('STATIC');

    final convertedTotal = inv.convertedTotalInr ?? ext?.convertedTotalInr ?? (origTotal * rate);
    final convertedTaxable = inv.convertedTaxableInr ?? ext?.convertedTaxableInr ?? (origTaxable * rate);

    final origin = inv.invoiceOrigin ?? 'FOREIGN_SERVICE';
    final isClassOverridden = inv.classificationOverride != null;

    return GlassCard(
      padding: const EdgeInsets.all(24),
      borderRadius: 20,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Section 1: Classification & Origin Evidence
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: const Color(0xFF0284C7).withValues(alpha: isDark ? 0.25 : 0.15),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.public_rounded, color: Color(0xFF38BDF8), size: 24),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Text('Foreign Service Classification & Evidence', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: const Color(0xFF0284C7).withValues(alpha: 0.2),
                            borderRadius: BorderRadius.circular(6),
                            border: Border.all(color: const Color(0xFF38BDF8).withValues(alpha: 0.5)),
                          ),
                          child: Text(
                            origin,
                            style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Color(0xFF38BDF8)),
                          ),
                        ),
                        if (isClassOverridden) ...[
                          const SizedBox(width: 6),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: const Color(0xFFF59E0B).withValues(alpha: 0.2),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text('OVERRIDDEN', style: TextStyle(fontSize: 9.5, fontWeight: FontWeight.w800, color: Color(0xFFF59E0B))),
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'Multi-evidence verification: Country, Tax ID, Service keywords, and Bank credentials',
                      style: TextStyle(fontSize: 11.5, color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
                    ),
                  ],
                ),
              ),
              OutlinedButton.icon(
                onPressed: () => _showClassificationOverrideDialog(context),
                icon: const Icon(Icons.edit_note_rounded, size: 16),
                label: const Text('Override Classification'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: const Color(0xFF38BDF8),
                  side: const BorderSide(color: Color(0xFF0284C7)),
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  textStyle: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),

          // Three-Tier Provenance Matrix: SYSTEM vs FINANCE OVERRIDE vs FINAL
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: isDark ? const Color(0xFF1E293B).withValues(alpha: 0.6) : const Color(0xFFF8FAFC),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: isDark ? const Color(0xFF334155) : const Color(0xFFE2E8F0)),
            ),
            child: Row(
              children: [
                Expanded(
                  child: _buildProvenanceColumn(
                    label: 'SYSTEM CLASSIFICATION',
                    value: isClassOverridden ? (inv.classificationSource == 'USER_OVERRIDE' ? 'SYSTEM (INITIAL)' : origin) : origin,
                    subtext: 'Algorithmic multi-evidence deduction',
                    isDark: isDark,
                  ),
                ),
                Container(height: 40, width: 1, color: isDark ? const Color(0xFF334155) : const Color(0xFFE2E8F0)),
                Expanded(
                  child: _buildProvenanceColumn(
                    label: 'FINANCE OVERRIDE',
                    value: isClassOverridden ? (inv.classificationOverride ?? 'None') : 'None',
                    subtext: isClassOverridden ? 'Reason: ${inv.classificationOverrideReason ?? 'Verified by Finance'}' : 'No override active',
                    isDark: isDark,
                    isHighlight: isClassOverridden,
                  ),
                ),
                Container(height: 40, width: 1, color: isDark ? const Color(0xFF334155) : const Color(0xFFE2E8F0)),
                Expanded(
                  child: _buildProvenanceColumn(
                    label: 'FINAL AUTHORITATIVE',
                    value: origin,
                    subtext: 'Used for tax/accounting pipelines',
                    isDark: isDark,
                    isSuccess: true,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // Classification Evidence Chips
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _buildEvidenceChip(Icons.flag_rounded, 'Vendor Country', ext?.vendorCountry ?? 'Overseas', isDark),
              if (ext?.vendorTaxId != null && ext!.vendorTaxId!.isNotEmpty)
                _buildEvidenceChip(Icons.badge_rounded, 'Foreign Tax ID', ext.vendorTaxId!, isDark),
              if (ext?.serviceDescription != null && ext!.serviceDescription!.isNotEmpty)
                _buildEvidenceChip(Icons.miscellaneous_services_rounded, 'Service Description', ext.serviceDescription!, isDark),
              if (ext?.servicePeriod != null && ext!.servicePeriod!.isNotEmpty)
                _buildEvidenceChip(Icons.date_range_rounded, 'Service Period', ext.servicePeriod!, isDark),
              if (ext?.bankDetails != null && ext!.bankDetails!.isNotEmpty)
                _buildEvidenceChip(Icons.account_balance_rounded, 'Bank / SWIFT', ext.bankDetails!.summaryText, isDark),
            ],
          ),

          const SizedBox(height: 24),
          const Divider(height: 1),
          const SizedBox(height: 24),

          // Section 2: FX Conversion & Single Boundary Presentation
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: const Color(0xFFF59E0B).withValues(alpha: isDark ? 0.25 : 0.15),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.currency_exchange_rounded, color: Color(0xFFF59E0B), size: 24),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Text('Forex (FX) Conversion Boundary', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
                        const SizedBox(width: 8),
                        if (isFallback)
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: const Color(0xFFDC2626).withValues(alpha: 0.2),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text('FALLBACK RATE', style: TextStyle(fontSize: 9.5, fontWeight: FontWeight.w800, color: Color(0xFFEF4444))),
                          )
                        else
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: const Color(0xFF10B981).withValues(alpha: 0.18),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(fxSource, style: const TextStyle(fontSize: 9.5, fontWeight: FontWeight.w800, color: Color(0xFF10B981))),
                          ),
                      ],
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'Single conversion boundary. Converted INR amount feeds all downstream TDS, GST/RCM, ITC & Journal engines.',
                      style: TextStyle(fontSize: 11.5, color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
                    ),
                  ],
                ),
              ),
              OutlinedButton.icon(
                onPressed: () => _showFxOverrideDialog(context),
                icon: const Icon(Icons.tune_rounded, size: 16),
                label: const Text('Override FX Rate'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: const Color(0xFFF59E0B),
                  side: const BorderSide(color: Color(0xFFF59E0B)),
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  textStyle: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),

          // FX Conversion Highlight Box
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: isDark
                    ? [const Color(0xFF1E293B), const Color(0xFF0F172A)]
                    : [const Color(0xFFF1F5F9), const Color(0xFFE2E8F0)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: isDark ? const Color(0xFF334155) : const Color(0xFFCBD5E1)),
            ),
            child: Column(
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    // Foreign Original
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('ORIGINAL FOREIGN AMOUNT', style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.bold, color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B))),
                        const SizedBox(height: 4),
                        Text(
                          '$origCurr ${NumberFormat("#,##0.00").format(origTotal)}',
                          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: Color(0xFF38BDF8)),
                        ),
                        Text('Taxable: $origCurr ${NumberFormat("#,##0.00").format(origTaxable)}', style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8))),
                        const SizedBox(height: 2),
                        Text('Invoice Date: ${ext?.invoiceDate ?? 'N/A'}', style: TextStyle(fontSize: 10, color: isDark ? const Color(0xFF64748B) : const Color(0xFF94A3B8))),
                      ],
                    ),
                    const Icon(Icons.close_rounded, size: 18, color: Color(0xFF94A3B8)),
                    // Exchange Rate
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: [
                        Text('FX RATE (${fxDate})', style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.bold, color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B))),
                        const SizedBox(height: 4),
                        Text(
                          rate.toStringAsFixed(6),
                          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: Color(0xFFF59E0B)),
                        ),
                        if (isOverridden)
                          Text('System Rate: ${origSysRate.toStringAsFixed(6)} (Finance Final)', style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: Color(0xFFF59E0B)))
                        else
                          Text('Source: $fxSource', style: const TextStyle(fontSize: 10, color: Color(0xFF94A3B8))),
                        const SizedBox(height: 2),
                        Text('Lookup: Invoice Date', style: const TextStyle(fontSize: 10, color: Color(0xFF10B981), fontWeight: FontWeight.w600)),
                      ],
                    ),
                    const Icon(Icons.arrow_forward_rounded, size: 18, color: Color(0xFF94A3B8)),
                    // Converted Canonical INR
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text('CANONICAL INR GROSS', style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.bold, color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B))),
                        const SizedBox(height: 4),
                        Text(
                          inrFormat.format(convertedTotal),
                          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: Color(0xFF10B981)),
                        ),
                        Text('Taxable INR: ${inrFormat.format(convertedTaxable)}', style: const TextStyle(fontSize: 11, color: Color(0xFF10B981))),
                        const SizedBox(height: 2),
                        Text('SSOT INR Boundary', style: TextStyle(fontSize: 10, color: isDark ? const Color(0xFF64748B) : const Color(0xFF94A3B8))),
                      ],
                    ),
                  ],
                ),
              ],
            ),
          ),

          // Statutory Compliance Guidance Strip for Foreign Invoices
          const SizedBox(height: 14),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: isDark ? const Color(0xFF0F172A).withValues(alpha: 0.6) : const Color(0xFFF8FAFC),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: isDark ? const Color(0xFF334155) : const Color(0xFFE2E8F0)),
            ),
            child: Row(
              children: [
                const Icon(Icons.verified_user_rounded, color: Color(0xFF38BDF8), size: 18),
                const SizedBox(width: 10),
                Expanded(
                  child: Wrap(
                    spacing: 12,
                    runSpacing: 6,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: const Color(0xFF0284C7).withValues(alpha: 0.15),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text('0% Vendor GST', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Color(0xFF0284C7))),
                          ),
                          const SizedBox(width: 6),
                          const Text('Overseas supplier does not charge Indian GST', style: TextStyle(fontSize: 11, color: Color(0xFF94A3B8))),
                        ],
                      ),
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: const Color(0xFF10B981).withValues(alpha: 0.15),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text('18% IGST RCM (Sec 5(3))', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Color(0xFF10B981))),
                          ),
                          const SizedBox(width: 6),
                          const Text('100% ITC Claimable', style: TextStyle(fontSize: 11, color: Color(0xFF94A3B8))),
                        ],
                      ),
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: const Color(0xFFF59E0B).withValues(alpha: 0.15),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text('TDS Sec 195/393', style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Color(0xFFF59E0B))),
                          ),
                          const SizedBox(width: 6),
                          const Text('Includes 4% Health & Education Cess', style: TextStyle(fontSize: 11, color: Color(0xFF94A3B8))),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

          if (isOverridden && inv.fxOverrideReason != null) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: const Color(0xFFF59E0B).withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: const Color(0xFFF59E0B).withValues(alpha: 0.3)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.info_outline_rounded, color: Color(0xFFF59E0B), size: 16),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'FX Override Audit: "${inv.fxOverrideReason}" (Original System Rate: ${origSysRate.toStringAsFixed(6)})',
                      style: const TextStyle(fontSize: 11.5, color: Color(0xFFF59E0B), fontWeight: FontWeight.w600),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildProvenanceColumn({
    required String label,
    required String value,
    required String subtext,
    required bool isDark,
    bool isHighlight = false,
    bool isSuccess = false,
  }) {
    Color valColor = isDark ? Colors.white : const Color(0xFF0F172A);
    if (isHighlight) valColor = const Color(0xFFF59E0B);
    if (isSuccess) valColor = const Color(0xFF10B981);

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 9.5, fontWeight: FontWeight.bold, color: Color(0xFF94A3B8))),
          const SizedBox(height: 4),
          Text(value, style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: valColor)),
          const SizedBox(height: 2),
          Text(subtext, style: const TextStyle(fontSize: 10, color: Color(0xFF94A3B8)), maxLines: 2, overflow: TextOverflow.ellipsis),
        ],
      ),
    );
  }

  Widget _buildEvidenceChip(IconData icon, String label, String value, bool isDark) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF1E293B) : const Color(0xFFF1F5F9),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: isDark ? const Color(0xFF334155) : const Color(0xFFE2E8F0)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: const Color(0xFF38BDF8)),
          const SizedBox(width: 6),
          Text('$label: ', style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: Color(0xFF94A3B8))),
          Text(value, style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: isDark ? Colors.white : const Color(0xFF0F172A))),
        ],
      ),
    );
  }
}
