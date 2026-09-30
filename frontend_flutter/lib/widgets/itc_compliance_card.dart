import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../models/invoice_models.dart';
import '../providers/invoice_provider.dart';
import 'glass_card.dart';

class ItcComplianceCard extends StatefulWidget {
  final ItcResult? itcResult;
  final double totalGstTax;

  const ItcComplianceCard({
    super.key,
    this.itcResult,
    required this.totalGstTax,
  });

  @override
  State<ItcComplianceCard> createState() => _ItcComplianceCardState();
}

class _ItcComplianceCardState extends State<ItcComplianceCard> {
  bool _isEditingDetails = false;

  Color _getStatusColor(String status) {
    switch (status.toUpperCase()) {
      case 'ELIGIBLE':
        return const Color(0xFF10B981);
      case 'PARTIALLY_ELIGIBLE':
        return Colors.amber;
      case 'INELIGIBLE':
      case 'BLOCKED':
        return Colors.redAccent;
      case 'REVIEW_REQUIRED':
      default:
        return Colors.orangeAccent;
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final currency = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);
    final provider = context.watch<InvoiceProvider>();

    final itc = provider.editableItc ??
        widget.itcResult ??
        ItcResult(
          status: 'ELIGIBLE',
          eligibleAmount: widget.totalGstTax,
          ineligibleAmount: 0.0,
          netItcAvailable: widget.totalGstTax,
          totalTaxAmount: widget.totalGstTax,
          reason: 'General input tax credit for business use u/s 16(1)',
          ruleReference: 'CGST Act Section 16',
        );

    final statusColor = _getStatusColor(itc.status);
    final total = widget.totalGstTax > 0 ? widget.totalGstTax : itc.totalTaxAmount;
    final eligible = (itc.status == 'ELIGIBLE')
        ? total
        : ((itc.netItcAvailable != null && itc.netItcAvailable! <= total)
            ? itc.netItcAvailable!
            : (itc.eligibleAmount <= total ? itc.eligibleAmount : total));
    final blocked = (total - eligible).clamp(0.0, total);

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
                    color: statusColor.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(Icons.verified_outlined, color: statusColor, size: 20),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(
                            'Input Tax Credit (ITC) Compliance',
                            style: theme.textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w700,
                              letterSpacing: 0.2,
                            ),
                          ),
                          const SizedBox(width: 8),
                          // Clickable Status Badge to Toggle / Change
                          PopupMenuButton<String>(
                            tooltip: 'Change ITC Eligibility Status',
                            initialValue: itc.status,
                            onSelected: (val) {
                              if (val == 'ELIGIBLE') {
                                provider.updateItc(
                                  status: val,
                                  eligibleAmount: total,
                                  ineligibleAmount: 0.0,
                                  netItcAvailable: total,
                                  reason: 'Eligible business input tax credit claimable under CGST Act Section 16(1).',
                                  ruleReference: 'CGST Act Section 16',
                                );
                              } else if (val == 'BLOCKED' || val == 'INELIGIBLE') {
                                provider.updateItc(
                                  status: val,
                                  eligibleAmount: 0.0,
                                  ineligibleAmount: total,
                                  netItcAvailable: 0.0,
                                  reason: 'Blocked credit under GST Act Section 17(5) (e.g. food/cabs/personal/gift).',
                                  ruleReference: 'CGST Act Section 17(5)',
                                );
                              } else {
                                provider.updateItc(status: val);
                              }
                            },
                            itemBuilder: (ctx) => [
                              const PopupMenuItem(value: 'ELIGIBLE', child: Text('ELIGIBLE (100% Claimable)')),
                              const PopupMenuItem(value: 'PARTIALLY_ELIGIBLE', child: Text('PARTIALLY ELIGIBLE')),
                              const PopupMenuItem(value: 'BLOCKED', child: Text('BLOCKED u/s 17(5)')),
                              const PopupMenuItem(value: 'REVIEW_REQUIRED', child: Text('REVIEW REQUIRED')),
                            ],
                            child: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: statusColor.withOpacity(0.15),
                                borderRadius: BorderRadius.circular(12),
                                border: Border.all(color: statusColor.withOpacity(0.4)),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Text(
                                    itc.status.replaceAll('_', ' '),
                                    style: theme.textTheme.labelSmall?.copyWith(
                                      color: statusColor,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                  const SizedBox(width: 4),
                                  Icon(Icons.arrow_drop_down, size: 14, color: statusColor),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ),
                      Text(
                        'GST Law Sections 16 & 17(5) Blocked Credit Determination',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.textTheme.bodySmall?.color?.withOpacity(0.7),
                        ),
                      ),
                    ],
                  ),
                ),
                // Toggle Editor Button
                IconButton(
                  tooltip: _isEditingDetails ? 'Hide Direct Editor' : 'Edit ITC Amounts & Rule',
                  icon: Icon(_isEditingDetails ? Icons.expand_less : Icons.tune_rounded, size: 20, color: const Color(0xFF10B981)),
                  onPressed: () {
                    setState(() => _isEditingDetails = !_isEditingDetails);
                  },
                ),
              ],
            ),

            // In-place Quick ITC Amounts Editor
            if (_isEditingDetails) ...[
              const SizedBox(height: 14),
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: theme.colorScheme.surfaceContainerHighest.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0xFF10B981).withOpacity(0.35)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text('Edit Statutory ITC Amounts (₹)', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Color(0xFF10B981))),
                        Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            TextButton.icon(
                              onPressed: () {
                                provider.updateItc(
                                  status: 'ELIGIBLE',
                                  eligibleAmount: total,
                                  ineligibleAmount: 0.0,
                                  netItcAvailable: total,
                                  ruleReference: 'CGST Act Section 16',
                                  reason: 'Eligible for business use under Section 16(1).',
                                );
                              },
                              icon: const Icon(Icons.check, size: 12),
                              label: const Text('100% Eligible', style: TextStyle(fontSize: 11)),
                            ),
                            const SizedBox(width: 4),
                            TextButton.icon(
                              onPressed: () {
                                provider.updateItc(
                                  status: 'BLOCKED',
                                  eligibleAmount: 0.0,
                                  ineligibleAmount: total,
                                  netItcAvailable: 0.0,
                                  ruleReference: 'CGST Act Section 17(5)',
                                  reason: 'Blocked input tax credit under Section 17(5).',
                                );
                              },
                              icon: const Icon(Icons.block, size: 12, color: Colors.redAccent),
                              label: const Text('100% Blocked', style: TextStyle(fontSize: 11, color: Colors.redAccent)),
                            ),
                          ],
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Expanded(
                          child: TextFormField(
                            key: ValueKey('itc_elig_${itc.eligibleAmount}'),
                            initialValue: itc.eligibleAmount.toStringAsFixed(2),
                            keyboardType: const TextInputType.numberWithOptions(decimal: true),
                            decoration: const InputDecoration(labelText: 'Eligible ITC (₹)', border: OutlineInputBorder(), isDense: true),
                            onChanged: (v) {
                              final val = double.tryParse(v) ?? 0.0;
                              provider.updateItc(eligibleAmount: val, netItcAvailable: val);
                            },
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: TextFormField(
                            key: ValueKey('itc_inelig_${itc.ineligibleAmount}'),
                            initialValue: itc.ineligibleAmount.toStringAsFixed(2),
                            keyboardType: const TextInputType.numberWithOptions(decimal: true),
                            decoration: const InputDecoration(labelText: 'Blocked Credit u/s 17(5) (₹)', border: OutlineInputBorder(), isDense: true),
                            onChanged: (v) {
                              final val = double.tryParse(v) ?? 0.0;
                              provider.updateItc(ineligibleAmount: val);
                            },
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: TextFormField(
                            key: ValueKey('itc_tot_${itc.totalTaxAmount}'),
                            initialValue: total.toStringAsFixed(2),
                            keyboardType: const TextInputType.numberWithOptions(decimal: true),
                            decoration: const InputDecoration(labelText: 'Total GST Tax on Bill (₹)', border: OutlineInputBorder(), isDense: true),
                            onChanged: (v) {
                              final val = double.tryParse(v) ?? 0.0;
                              provider.updateItc(totalTaxAmount: val);
                            },
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    TextFormField(
                      key: ValueKey('itc_reason_${itc.reason}'),
                      initialValue: itc.reason ?? '',
                      decoration: const InputDecoration(
                        labelText: 'ITC Statutory Determination & Rationale',
                        border: OutlineInputBorder(),
                        isDense: true,
                        hintText: 'e.g. Eligible business expense under Section 16(1)...',
                      ),
                      onChanged: (v) {
                        provider.updateItc(reason: v);
                      },
                    ),
                  ],
                ),
              ),
            ],

            const SizedBox(height: 16),
            const Divider(height: 1),
            const SizedBox(height: 16),

            // Summary Metrics Row
            LayoutBuilder(
              builder: (context, constraints) {
                final isNarrow = constraints.maxWidth < 600;

                final widgets = [
                  // 1. Total GST on Bill
                  _buildItcStat(
                    context,
                    label: 'Total GST Tax on Bill',
                    value: currency.format(total),
                    subtitle: 'Tax charged / RCM tax',
                    icon: Icons.receipt_long_outlined,
                    color: Colors.blueAccent,
                  ),
                  const SizedBox(width: 8),
                  // 2. Eligible to Claim
                  _buildItcStat(
                    context,
                    label: 'Eligible ITC (Claim in GSTR-3B)',
                    value: currency.format(eligible),
                    subtitle: blocked == 0 ? '100% Available to offset tax' : 'Claimable portion',
                    icon: Icons.check_circle_outline,
                    color: const Color(0xFF10B981),
                    isHighlight: true,
                  ),
                  const SizedBox(width: 8),
                  // 3. Blocked / Ineligible
                  _buildItcStat(
                    context,
                    label: 'Blocked Credit u/s 17(5)',
                    value: currency.format(blocked),
                    subtitle: blocked == 0 ? 'No blocked items (Eligible)' : 'Ineligible by GST Law',
                    icon: blocked > 0 ? Icons.block : Icons.lock_open_outlined,
                    color: blocked > 0 ? Colors.redAccent : Colors.grey,
                  ),
                ];

                if (isNarrow) {
                  return Column(
                    children: [
                      widgets[0],
                      const SizedBox(height: 8),
                      widgets[2],
                      const SizedBox(height: 8),
                      widgets[4],
                    ],
                  );
                }

                return Row(
                  children: [
                    Expanded(child: widgets[0]),
                    widgets[1],
                    Expanded(child: widgets[2]),
                    widgets[3],
                    Expanded(child: widgets[4]),
                  ],
                );
              },
            ),

            const SizedBox(height: 14),

            // Plain-English Explanation Banner
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: (itc.ineligibleAmount > 0 ? Colors.amber : const Color(0xFF10B981)).withOpacity(0.08),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: (itc.ineligibleAmount > 0 ? Colors.amber : const Color(0xFF10B981)).withOpacity(0.25),
                ),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(
                    itc.ineligibleAmount > 0 ? Icons.warning_amber_rounded : Icons.info_outline,
                    size: 16,
                    color: itc.ineligibleAmount > 0 ? Colors.amber : const Color(0xFF10B981),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          itc.ineligibleAmount > 0
                              ? 'Partial / Blocked ITC Determination'
                              : 'What is ITC (Input Tax Credit)?',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                            color: itc.ineligibleAmount > 0 ? Colors.amber.shade200 : const Color(0xFF10B981),
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          itc.reason != null && itc.reason!.isNotEmpty
                              ? '${itc.ruleReference ?? "Section 16(1)"}: ${itc.reason}'
                              : 'This is a genuine business expense. The full GST amount paid can be claimed as a tax credit (ITC) in your monthly GSTR-3B return to reduce your output tax payable.',
                          style: TextStyle(
                            fontSize: 11,
                            color: theme.textTheme.bodyMedium?.color?.withOpacity(0.85),
                            height: 1.3,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),

            if (itc.lineItemBreakdown.isNotEmpty) ...[
              const SizedBox(height: 16),
              Text(
                'Line-Level Statutory Classification',
                style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 8),
              ListView.separated(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: itc.lineItemBreakdown.length,
                separatorBuilder: (_, __) => const Divider(height: 1),
                itemBuilder: (context, idx) {
                  final line = itc.lineItemBreakdown[idx];
                  final lColor = _getStatusColor(line.itcStatus);
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          width: 20,
                          height: 20,
                          alignment: Alignment.center,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: theme.dividerColor.withOpacity(0.2),
                          ),
                          child: Text('${line.lineIndex}', style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold)),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(line.description, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                              if (line.reason.isNotEmpty)
                                Text(line.reason, style: TextStyle(fontSize: 11, color: theme.textTheme.bodySmall?.color)),
                            ],
                          ),
                        ),
                        const SizedBox(width: 8),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            Text(currency.format(line.eligibleAmount), style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: lColor)),
                            Text(line.itcStatus, style: TextStyle(fontSize: 10, color: lColor)),
                          ],
                        ),
                      ],
                    ),
                  );
                },
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildItcStat(
    BuildContext context, {
    required String label,
    required String value,
    required String subtitle,
    required IconData icon,
    required Color color,
    bool isHighlight = false,
  }) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.25)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 14, color: color),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  label,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: theme.textTheme.bodySmall?.color,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: TextStyle(
              fontWeight: FontWeight.bold,
              fontSize: isHighlight ? 16 : 14,
              color: color,
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
