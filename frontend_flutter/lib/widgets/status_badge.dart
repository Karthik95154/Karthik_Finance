import 'package:flutter/material.dart';

class StatusBadge extends StatefulWidget {
  final String status;
  final bool isSmall;
  final bool pulse;

  const StatusBadge({
    super.key,
    required this.status,
    this.isSmall = false,
    this.pulse = true,
  });

  @override
  State<StatusBadge> createState() => _StatusBadgeState();
}

class _StatusBadgeState extends State<StatusBadge> with SingleTickerProviderStateMixin {
  late AnimationController _animController;
  late Animation<double> _pulseAnim;

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1800),
    )..repeat(reverse: true);

    _pulseAnim = Tween<double>(begin: 0.35, end: 1.0).animate(
      CurvedAnimation(parent: _animController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _animController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    Color bg;
    Color fg;
    Color borderColor;
    String label;
    IconData icon;

    final norm = widget.status.trim().toLowerCase();
    switch (norm) {
      case 'approved':
      case 'completed':
        bg = isDark ? const Color(0xFF10B981).withValues(alpha: 0.18) : const Color(0xFFD1FAE5);
        fg = isDark ? const Color(0xFF34D399) : const Color(0xFF065F46);
        borderColor = isDark ? const Color(0xFF10B981).withValues(alpha: 0.4) : const Color(0xFFA7F3D0);
        label = 'Approved';
        icon = Icons.check_circle_outline_rounded;
        break;
      case 'exported':
      case 'exported_zoho':
        bg = isDark ? const Color(0xFF6366F1).withValues(alpha: 0.18) : const Color(0xFFEEF2FF);
        fg = isDark ? const Color(0xFF818CF8) : const Color(0xFF3730A3);
        borderColor = isDark ? const Color(0xFF6366F1).withValues(alpha: 0.4) : const Color(0xFFC7D2FE);
        label = 'Exported to Zoho';
        icon = Icons.cloud_done_outlined;
        break;
      case 'processing':
      case 'processing_vlm':
      case 'processing_accounting':
        bg = isDark ? const Color(0xFF06B6D4).withValues(alpha: 0.18) : const Color(0xFFCFFAFE);
        fg = isDark ? const Color(0xFF22D3EE) : const Color(0xFF155E75);
        borderColor = isDark ? const Color(0xFF06B6D4).withValues(alpha: 0.4) : const Color(0xFFA5F3FC);
        label = 'Processing AI';
        icon = Icons.autorenew_rounded;
        break;
      case 'failed':
      case 'rejected':
        bg = isDark ? const Color(0xFFF43F5E).withValues(alpha: 0.18) : const Color(0xFFFFE4E6);
        fg = isDark ? const Color(0xFFFB7185) : const Color(0xFF9F1239);
        borderColor = isDark ? const Color(0xFFF43F5E).withValues(alpha: 0.4) : const Color(0xFFFECDD3);
        label = 'Failed';
        icon = Icons.error_outline_rounded;
        break;
      case 'hitl_review':
      case 'final_hitl_review':
        bg = isDark ? const Color(0xFF8B5CF6).withValues(alpha: 0.18) : const Color(0xFFF3E8FF);
        fg = isDark ? const Color(0xFFA78BFA) : const Color(0xFF6B21A8);
        borderColor = isDark ? const Color(0xFF8B5CF6).withValues(alpha: 0.4) : const Color(0xFFDDD6FE);
        label = 'HITL Review';
        icon = Icons.rate_review_outlined;
        break;
      case 'pending':
      case 'pending_review':
      case 'staged':
      case 'not_processed':
      case 'needs_review':
      default:
        bg = isDark ? const Color(0xFFF59E0B).withValues(alpha: 0.18) : const Color(0xFFFEF3C7);
        fg = isDark ? const Color(0xFFFBBF24) : const Color(0xFF92400E);
        borderColor = isDark ? const Color(0xFFF59E0B).withValues(alpha: 0.4) : const Color(0xFFFDE68A);
        label = 'Pending Review';
        icon = Icons.schedule_rounded;
        break;
    }

    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: widget.isSmall ? 8 : 12,
        vertical: widget.isSmall ? 3 : 5,
      ),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: borderColor, width: 1),
        boxShadow: [
          BoxShadow(
            color: fg.withValues(alpha: isDark ? 0.15 : 0.04),
            blurRadius: 6,
            offset: const Offset(0, 1),
          ),
        ],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (widget.pulse)
            AnimatedBuilder(
              animation: _pulseAnim,
              builder: (context, child) {
                return Container(
                  width: widget.isSmall ? 6 : 7,
                  height: widget.isSmall ? 6 : 7,
                  margin: const EdgeInsets.only(right: 6),
                  decoration: BoxDecoration(
                    color: fg.withValues(alpha: _pulseAnim.value),
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: fg.withValues(alpha: _pulseAnim.value * 0.8),
                        blurRadius: 6,
                        spreadRadius: 1,
                      ),
                    ],
                  ),
                );
              },
            )
          else
            Padding(
              padding: const EdgeInsets.only(right: 5),
              child: Icon(icon, size: widget.isSmall ? 12 : 14, color: fg),
            ),
          Text(
            label,
            style: TextStyle(
              color: fg,
              fontSize: widget.isSmall ? 11 : 12,
              fontWeight: FontWeight.w600,
              letterSpacing: -0.2,
            ),
          ),
        ],
      ),
    );
  }
}

/// ProvenanceBadge shows the source of information: AI Extracted, Rule Engine, or Verified
enum ProvenanceType { aiExtracted, ruleEngine, verified }

class ProvenanceBadge extends StatelessWidget {
  final ProvenanceType type;
  final String? customLabel;
  final bool isSmall;

  const ProvenanceBadge({
    super.key,
    required this.type,
    this.customLabel,
    this.isSmall = true,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    Color bg;
    Color fg;
    Color border;
    String defaultLabel;

    switch (type) {
      case ProvenanceType.aiExtracted:
        bg = isDark ? const Color(0xFF8B5CF6).withValues(alpha: 0.18) : const Color(0xFFF3E8FF);
        fg = isDark ? const Color(0xFFA78BFA) : const Color(0xFF7C3AED);
        border = isDark ? const Color(0xFF8B5CF6).withValues(alpha: 0.4) : const Color(0xFFDDD6FE);
        defaultLabel = '🤖 AI Extracted';
        break;
      case ProvenanceType.ruleEngine:
        bg = isDark ? const Color(0xFF2563EB).withValues(alpha: 0.18) : const Color(0xFFEFF6FF);
        fg = isDark ? const Color(0xFF60A5FA) : const Color(0xFF2563EB);
        border = isDark ? const Color(0xFF2563EB).withValues(alpha: 0.4) : const Color(0xFFBFDBFE);
        defaultLabel = '⚙ Rule Engine';
        break;
      case ProvenanceType.verified:
        bg = isDark ? const Color(0xFF10B981).withValues(alpha: 0.18) : const Color(0xFFECFDF5);
        fg = isDark ? const Color(0xFF34D399) : const Color(0xFF059669);
        border = isDark ? const Color(0xFF10B981).withValues(alpha: 0.4) : const Color(0xFFA7F3D0);
        defaultLabel = '✓ Verified';
        break;
    }

    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: isSmall ? 7 : 10,
        vertical: isSmall ? 2.5 : 4,
      ),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: border, width: 1),
      ),
      child: Text(
        customLabel ?? defaultLabel,
        style: TextStyle(
          color: fg,
          fontSize: isSmall ? 10.5 : 11.5,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.1,
        ),
      ),
    );
  }
}

/// ComplianceBadge displays verified statutory indicators like "✓ GST Valid", "✓ ITC Eligible", "⚠ TDS Threshold", "✓ RCM N/A"
class ComplianceBadge extends StatelessWidget {
  final String label;
  final bool isValid;
  final bool isWarning;

  const ComplianceBadge({
    super.key,
    required this.label,
    this.isValid = true,
    this.isWarning = false,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    Color bg;
    Color fg;
    Color border;

    if (isWarning) {
      bg = isDark ? const Color(0xFFF59E0B).withValues(alpha: 0.18) : const Color(0xFFFEF3C7);
      fg = isDark ? const Color(0xFFFBBF24) : const Color(0xFF92400E);
      border = isDark ? const Color(0xFFF59E0B).withValues(alpha: 0.4) : const Color(0xFFFDE68A);
    } else if (isValid) {
      bg = isDark ? const Color(0xFF10B981).withValues(alpha: 0.18) : const Color(0xFFECFDF5);
      fg = isDark ? const Color(0xFF34D399) : const Color(0xFF065F46);
      border = isDark ? const Color(0xFF10B981).withValues(alpha: 0.4) : const Color(0xFFA7F3D0);
    } else {
      bg = isDark ? const Color(0xFFF43F5E).withValues(alpha: 0.18) : const Color(0xFFFFE4E6);
      fg = isDark ? const Color(0xFFFB7185) : const Color(0xFF9F1239);
      border = isDark ? const Color(0xFFF43F5E).withValues(alpha: 0.4) : const Color(0xFFFECDD3);
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: border, width: 1),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: fg,
          fontSize: 11,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.1,
        ),
      ),
    );
  }
}
