import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../models/invoice_models.dart';
import 'glass_card.dart';

class FinancialValidationCard extends StatelessWidget {
  final FinancialValidationResult? validationResult;

  const FinancialValidationCard({
    super.key,
    this.validationResult,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final currency = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);
    final result = validationResult;

    if (result == null || result.checks.isEmpty) {
      return const SizedBox.shrink();
    }

    final isPassed = result.overallStatus.toUpperCase() == 'PASSED';

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
                    color: (isPassed ? const Color(0xFF10B981) : Colors.amber).withOpacity(0.15),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(
                    isPassed ? Icons.check_circle_outline : Icons.rule_folder_outlined,
                    color: isPassed ? const Color(0xFF10B981) : Colors.amber,
                    size: 20,
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
                            'Financial Validation & Mathematical Reconciliation',
                            style: theme.textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w700,
                              letterSpacing: 0.2,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: (isPassed ? const Color(0xFF10B981) : Colors.amber).withOpacity(0.15),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(
                                color: (isPassed ? const Color(0xFF10B981) : Colors.amber).withOpacity(0.4),
                              ),
                            ),
                            child: Text(
                              result.overallStatus,
                              style: theme.textTheme.labelSmall?.copyWith(
                                color: isPassed ? const Color(0xFF10B981) : Colors.amber,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                        ],
                      ),
                      Text(
                        'Header vs Line Items Cross-Validation (Tolerance ±₹${result.tolerance})',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.textTheme.bodySmall?.color?.withOpacity(0.7),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),

            const SizedBox(height: 16),
            const Divider(height: 1),
            const SizedBox(height: 12),

            // Checks list
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: result.checks.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (context, idx) {
                final check = result.checks[idx];
                final checkPassed = check.status.toUpperCase() == 'PASSED';

                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: Row(
                    children: [
                      Icon(
                        checkPassed ? Icons.check_circle : Icons.error_outline,
                        size: 16,
                        color: checkPassed ? const Color(0xFF10B981) : Colors.amber,
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              check.name.replaceAll('_', ' ').toUpperCase(),
                              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                            ),
                            if (check.description.isNotEmpty)
                              Text(
                                check.description,
                                style: TextStyle(fontSize: 11, color: theme.textTheme.bodySmall?.color),
                              ),
                          ],
                        ),
                      ),
                      if (check.difference != null && check.difference != 0)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: Colors.amber.withOpacity(0.1),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            'Diff: ${currency.format(check.difference)}',
                            style: const TextStyle(fontSize: 11, color: Colors.amber, fontWeight: FontWeight.bold),
                          ),
                        ),
                      const SizedBox(width: 8),
                      Text(
                        check.status,
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          color: checkPassed ? const Color(0xFF10B981) : Colors.amber,
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}
