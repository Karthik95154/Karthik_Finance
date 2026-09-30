import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../config/theme.dart';
import '../models/audit_models.dart';
import '../providers/invoice_provider.dart';
import 'glass_card.dart';
import 'skeleton_loader.dart';

class AuditTrailViewWidget extends StatefulWidget {
  final dynamic invoiceId;

  const AuditTrailViewWidget({super.key, required this.invoiceId});

  @override
  State<AuditTrailViewWidget> createState() => _AuditTrailViewWidgetState();
}

class _AuditTrailViewWidgetState extends State<AuditTrailViewWidget> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<InvoiceProvider>(context, listen: false).fetchAuditTrail(widget.invoiceId);
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final invProv = Provider.of<InvoiceProvider>(context);
    final logs = invProv.auditTrail;
    final isLoading = invProv.isLoadingAudit;
    final dateFormat = DateFormat('dd MMM yyyy, hh:mm:ss a');

    if (isLoading && logs.isEmpty) {
      return const AuditTrailSkeleton();
    }

    return GlassCard(
      padding: const EdgeInsets.all(24),
      borderRadius: 20,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppTheme.primaryColor.withValues(alpha: isDark ? 0.2 : 0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.history_edu_rounded, size: 20, color: AppTheme.primaryLight),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Immutable Audit Trail', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
                    const SizedBox(height: 2),
                    Text(
                      'Cryptographic audit trail tracking all lifecycle events, extraction modifications, approvals, and ERP exports',
                      style: TextStyle(fontSize: 11.5, color: isDark ? AppTheme.darkTextMuted : const Color(0xFF64748B)),
                    ),
                  ],
                ),
              ),
              IconButton(
                onPressed: () => invProv.fetchAuditTrail(widget.invoiceId),
                icon: const Icon(Icons.refresh_rounded, size: 18),
                tooltip: 'Refresh Audit Trail',
              ),
            ],
          ),
          const SizedBox(height: 20),

          if (logs.isEmpty) ...[
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: isDark ? const Color(0xFF0F172A).withValues(alpha: 0.5) : const Color(0xFFF8FAFC),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0)),
              ),
              child: const Center(
                child: Column(
                  children: [
                    Icon(Icons.assignment_turned_in_outlined, size: 36, color: Color(0xFF94A3B8)),
                    SizedBox(height: 10),
                    Text('Initial audit event logged upon document ingestion.', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                  ],
                ),
              ),
            ),
          ] else ...[
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: logs.length,
              separatorBuilder: (_, index) => const SizedBox(height: 12),
              itemBuilder: (context, index) {
                final log = logs[index];
                final isLast = index == logs.length - 1;

                return _buildTimelineItem(log, isLast, dateFormat, isDark);
              },
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildTimelineItem(AuditLogEntry log, bool isLast, DateFormat dateFormat, bool isDark) {
    Color actionColor = AppTheme.primaryColor;
    IconData actionIcon = Icons.info_outline_rounded;

    final actUpper = log.action.toUpperCase();
    if (actUpper.contains('UPLOAD') || actUpper.contains('CREATE')) {
      actionColor = const Color(0xFF3B82F6);
      actionIcon = Icons.cloud_upload_outlined;
    } else if (actUpper.contains('APPROVE')) {
      actionColor = AppTheme.accentColor;
      actionIcon = Icons.verified_rounded;
    } else if (actUpper.contains('EXPORT')) {
      actionColor = const Color(0xFF10B981);
      actionIcon = Icons.send_rounded;
    } else if (actUpper.contains('REJECT') || actUpper.contains('CANCEL')) {
      actionColor = AppTheme.errorColor;
      actionIcon = Icons.cancel_outlined;
    } else if (actUpper.contains('EDIT') || actUpper.contains('UPDATE')) {
      actionColor = const Color(0xFFF59E0B);
      actionIcon = Icons.edit_note_rounded;
    }

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF0F172A).withValues(alpha: 0.5) : const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: actionColor.withValues(alpha: isDark ? 0.2 : 0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(actionIcon, size: 16, color: actionColor),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: actionColor.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        log.action,
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w800,
                          color: actionColor,
                        ),
                      ),
                    ),
                    const Spacer(),
                    if (log.createdAt != null)
                      Text(
                        dateFormat.format(log.createdAt!),
                        style: TextStyle(
                          fontSize: 11,
                          color: isDark ? AppTheme.darkTextMuted : const Color(0xFF64748B),
                        ),
                      ),
                  ],
                ),
                if (log.reason != null && log.reason!.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text(
                    log.reason!,
                    style: TextStyle(
                      fontSize: 12.5,
                      fontWeight: FontWeight.w600,
                      color: isDark ? Colors.white : const Color(0xFF0F172A),
                    ),
                  ),
                ],
                if (log.fieldName != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    'Field: ${log.fieldName} • Changed from "${log.beforeValue ?? "None"}" to "${log.afterValue ?? "None"}"',
                    style: TextStyle(
                      fontSize: 11.5,
                      color: isDark ? AppTheme.darkTextMuted : const Color(0xFF64748B),
                    ),
                  ),
                ],
                if (log.userEmail != null && log.userEmail!.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      const Icon(Icons.person_outline_rounded, size: 13, color: Color(0xFF94A3B8)),
                      const SizedBox(width: 4),
                      Text(
                        log.userEmail!,
                        style: TextStyle(
                          fontSize: 11,
                          color: isDark ? AppTheme.darkTextMuted : const Color(0xFF64748B),
                        ),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
