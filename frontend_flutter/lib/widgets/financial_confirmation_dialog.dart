import 'package:flutter/material.dart';

class FinancialFieldComparison {
  final String label;
  final String currentValue;
  final String proposedValue;
  final String? difference;
  final bool isDifferent;
  final String? note;

  const FinancialFieldComparison({
    required this.label,
    required this.currentValue,
    required this.proposedValue,
    this.difference,
    this.isDifferent = false,
    this.note,
  });
}

/// Displays a high-security financial confirmation dialog requiring explicit user approval
/// before altering any extracted invoice financial values.
Future<bool> showFinancialConfirmationDialog({
  required BuildContext context,
  required String actionTitle,
  required String reason,
  String? formulaExplanation,
  required List<FinancialFieldComparison> comparisons,
  List<Widget>? additionalContent,
  String confirmButtonText = 'Confirm & Apply Replacement',
  String cancelButtonText = 'Cancel & Keep Original Invoice Data',
  bool isCriticalChange = true,
}) async {
  final result = await showDialog<bool>(
    context: context,
    barrierDismissible: false,
    builder: (dialogCtx) {
      final theme = Theme.of(dialogCtx);
      final isDark = theme.brightness == Brightness.dark;

      return Dialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        elevation: 12,
        backgroundColor: isDark ? const Color(0xFF1E293B) : Colors.white,
        child: Container(
          width: 680,
          constraints: const BoxConstraints(maxHeight: 700),
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header with statutory warning badge
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: isCriticalChange
                          ? const Color(0xFFEF4444).withValues(alpha: 0.15)
                          : const Color(0xFFF59E0B).withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Icon(
                      isCriticalChange ? Icons.warning_amber_rounded : Icons.gavel_rounded,
                      color: isCriticalChange ? const Color(0xFFEF4444) : const Color(0xFFD97706),
                      size: 26,
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                actionTitle,
                                style: theme.textTheme.titleLarge?.copyWith(
                                  fontWeight: FontWeight.bold,
                                  fontSize: 18,
                                ),
                              ),
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                              decoration: BoxDecoration(
                                color: isDark
                                    ? const Color(0xFF78350F).withValues(alpha: 0.5)
                                    : const Color(0xFFFEF3C7),
                                borderRadius: BorderRadius.circular(6),
                                border: Border.all(color: const Color(0xFFF59E0B)),
                              ),
                              child: const Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(Icons.shield_outlined, size: 12, color: Color(0xFFD97706)),
                                  SizedBox(width: 4),
                                  Text(
                                    'FINANCIAL AUDIT SAFETY',
                                    style: TextStyle(
                                      fontSize: 9.5,
                                      fontWeight: FontWeight.bold,
                                      color: Color(0xFFD97706),
                                      letterSpacing: 0.4,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Careful: Modifying company financial & invoice records.',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: isDark ? const Color(0xFFFCA5A5) : const Color(0xFFDC2626),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 16),

              // Reason banner
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                decoration: BoxDecoration(
                  color: isDark ? const Color(0xFF0F172A) : const Color(0xFFF8FAFC),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                    color: isDark ? const Color(0xFF334155) : const Color(0xFFE2E8F0),
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Reason for Proposed Replacement:',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        color: theme.colorScheme.primary,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      reason,
                      style: TextStyle(
                        fontSize: 12.5,
                        color: isDark ? const Color(0xFFE2E8F0) : const Color(0xFF334155),
                        height: 1.3,
                      ),
                    ),
                    if (formulaExplanation != null && formulaExplanation.isNotEmpty) ...[
                      const SizedBox(height: 6),
                      Text(
                        'Calculation Basis: $formulaExplanation',
                        style: TextStyle(
                          fontSize: 11,
                          fontStyle: FontStyle.italic,
                          color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B),
                        ),
                      ),
                    ],
                  ],
                ),
              ),

              const SizedBox(height: 16),

              // Comparison Table Title
              Row(
                children: [
                  const Icon(Icons.compare_arrows_rounded, size: 16, color: Color(0xFF0284C7)),
                  const SizedBox(width: 6),
                  Text(
                    'Exact Field Replacements (Before vs After)',
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.bold,
                      color: isDark ? Colors.white : const Color(0xFF0F172A),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),

              // Comparison Table
              Flexible(
                child: Container(
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: isDark ? const Color(0xFF334155) : const Color(0xFFE2E8F0),
                    ),
                  ),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: SingleChildScrollView(
                      child: Table(
                        columnWidths: const {
                          0: FlexColumnWidth(2.2),
                          1: FlexColumnWidth(2.0),
                          2: FlexColumnWidth(2.0),
                          3: FlexColumnWidth(1.6),
                        },
                        defaultVerticalAlignment: TableCellVerticalAlignment.middle,
                        children: [
                          // Header Row
                          TableRow(
                            decoration: BoxDecoration(
                              color: isDark ? const Color(0xFF0F172A) : const Color(0xFFF1F5F9),
                            ),
                            children: const [
                              Padding(
                                padding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                                child: Text('FIELD', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
                              ),
                              Padding(
                                padding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                                child: Text('CURRENT / EXTRACTED', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
                              ),
                              Padding(
                                padding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                                child: Text('PROPOSED NEW', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
                              ),
                              Padding(
                                padding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                                child: Text('VARIANCE (Δ)', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
                              ),
                            ],
                          ),

                          // Data Rows
                          ...comparisons.map((c) {
                            return TableRow(
                              decoration: BoxDecoration(
                                color: c.isDifferent
                                    ? (isDark
                                        ? const Color(0xFF78350F).withValues(alpha: 0.15)
                                        : const Color(0xFFFFFBEB))
                                    : Colors.transparent,
                                border: Border(
                                  top: BorderSide(
                                    color: isDark ? const Color(0xFF334155) : const Color(0xFFE2E8F0),
                                    width: 0.7,
                                  ),
                                ),
                              ),
                              children: [
                                Padding(
                                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        c.label,
                                        style: TextStyle(
                                          fontSize: 12,
                                          fontWeight: c.isDifferent ? FontWeight.bold : FontWeight.normal,
                                        ),
                                      ),
                                      if (c.note != null && c.note!.isNotEmpty)
                                        Text(
                                          c.note!,
                                          style: const TextStyle(fontSize: 10, color: Colors.grey),
                                        ),
                                    ],
                                  ),
                                ),
                                Padding(
                                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                                  child: Text(
                                    c.currentValue,
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: c.isDifferent
                                          ? (isDark ? const Color(0xFFFCA5A5) : const Color(0xFFDC2626))
                                          : null,
                                      fontWeight: c.isDifferent ? FontWeight.w600 : FontWeight.normal,
                                    ),
                                  ),
                                ),
                                Padding(
                                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                                  child: Text(
                                    c.proposedValue,
                                    style: TextStyle(
                                      fontSize: 12,
                                      fontWeight: FontWeight.bold,
                                      color: c.isDifferent
                                          ? (isDark ? const Color(0xFF34D399) : const Color(0xFF059669))
                                          : null,
                                    ),
                                  ),
                                ),
                                Padding(
                                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                                  child: Text(
                                    c.difference ?? '-',
                                    style: TextStyle(
                                      fontSize: 11.5,
                                      fontWeight: FontWeight.bold,
                                      color: c.isDifferent
                                          ? const Color(0xFFD97706)
                                          : (isDark ? Colors.grey : Colors.black45),
                                    ),
                                  ),
                                ),
                              ],
                            );
                          }),
                        ],
                      ),
                    ),
                  ),
                ),
              ),

              if (additionalContent != null && additionalContent.isNotEmpty) ...[
                const SizedBox(height: 12),
                ...additionalContent,
              ],

              const SizedBox(height: 20),

              // Action Buttons
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  OutlinedButton.icon(
                    onPressed: () => Navigator.of(dialogCtx).pop(false),
                    icon: const Icon(Icons.close_rounded, size: 16),
                    label: Text(cancelButtonText),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    ),
                  ),
                  const SizedBox(width: 12),
                  ElevatedButton.icon(
                    onPressed: () => Navigator.of(dialogCtx).pop(true),
                    icon: const Icon(Icons.check_circle_outline, size: 16),
                    label: Text(confirmButtonText),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: isCriticalChange ? const Color(0xFFD97706) : const Color(0xFF0284C7),
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                      textStyle: const TextStyle(fontWeight: FontWeight.bold),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      );
    },
  );

  return result == true;
}
