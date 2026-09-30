import 'package:flutter/material.dart';
import 'glass_card.dart';

class PipelineProgressCard extends StatelessWidget {
  final String status;
  final String? accountingStatus;
  final String? approvalStatus;
  final String? exportStatus;
  final double? confidence;

  const PipelineProgressCard({
    super.key,
    required this.status,
    this.accountingStatus,
    this.approvalStatus,
    this.exportStatus,
    this.confidence,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    // Stages:
    // 1: Ingestion & Upload
    // 2: OpenAI / VLM Extraction
    // 3: GST & RCM Tax Engine
    // 4: Chart of Accounts & Master Data
    // 5: Statutory TDS & Threshold YTD
    // 6: ITC Section 16/17(5) & Balanced Journal

    final isProcessing = status.toUpperCase().startsWith('PROCESSING');
    final isVlmDone = status != 'PENDING' && status != 'PROCESSING_VLM';
    final isAcctDone = accountingStatus == 'COMPLETED' || status == 'COMPLETED' || approvalStatus != null;
    final isApproved = approvalStatus == 'APPROVED';
    final isExported = exportStatus == 'EXPORTED';

    final stages = [
      {'name': 'Document Ingestion', 'done': true, 'active': false},
      {'name': 'VLM Extraction', 'done': isVlmDone, 'active': status == 'PROCESSING_VLM'},
      {'name': 'GST & RCM Validation', 'done': isVlmDone, 'active': false},
      {'name': 'COA Ledger Mapping', 'done': isAcctDone, 'active': accountingStatus == 'PROCESSING_ACCOUNTING'},
      {'name': 'Statutory TDS & YTD', 'done': isAcctDone, 'active': false},
      {'name': 'ITC & Balanced Journal', 'done': isAcctDone, 'active': false},
    ];

    return GlassCard(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    const Icon(Icons.bolt, color: Colors.amber, size: 20),
                    const SizedBox(width: 8),
                    Text(
                      'Automated Statutory Pipeline Status',
                      style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.bold),
                    ),
                  ],
                ),
                if (confidence != null && confidence! > 0)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: Colors.blue.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Text(
                      'AI Confidence: ${(confidence! * (confidence! <= 1.0 ? 100 : 1)).toStringAsFixed(0)}%',
                      style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.blueAccent),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 14),
            // Step chips row
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: List.generate(stages.length, (idx) {
                  final s = stages[idx];
                  final isDone = s['done'] as bool;
                  final isActive = s['active'] as bool;

                  Color color = Colors.grey;
                  IconData icon = Icons.circle_outlined;
                  if (isDone) {
                    color = const Color(0xFF10B981);
                    icon = Icons.check_circle;
                  } else if (isActive) {
                    color = Colors.amber;
                    icon = Icons.hourglass_top_rounded;
                  }

                  return Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        decoration: BoxDecoration(
                          color: color.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: color.withOpacity(0.3)),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(icon, size: 14, color: color),
                            const SizedBox(width: 6),
                            Text(
                              'Stage ${idx + 1}: ${s['name']}',
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                color: color,
                              ),
                            ),
                          ],
                        ),
                      ),
                      if (idx < stages.length - 1)
                        Container(
                          width: 14,
                          height: 2,
                          color: theme.dividerColor.withOpacity(0.4),
                          margin: const EdgeInsets.symmetric(horizontal: 4),
                        ),
                    ],
                  );
                }),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
