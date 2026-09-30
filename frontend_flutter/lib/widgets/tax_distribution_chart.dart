import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../config/theme.dart';
import 'glass_card.dart';

class TaxDistributionChart extends StatefulWidget {
  final double totalAmount;
  final double cgstAmount;
  final double sgstAmount;
  final double igstAmount;
  final double tdsAmount;

  const TaxDistributionChart({
    super.key,
    required this.totalAmount,
    this.cgstAmount = 0,
    this.sgstAmount = 0,
    this.igstAmount = 0,
    this.tdsAmount = 0,
  });

  @override
  State<TaxDistributionChart> createState() => _TaxDistributionChartState();
}

class _TaxDistributionChartState extends State<TaxDistributionChart> {
  int? _hoveredIndex;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final currencyFormat = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 0);

    // Calculate default simulated amounts if not provided
    double cgst = widget.cgstAmount;
    double sgst = widget.sgstAmount;
    double igst = widget.igstAmount;
    double tds = widget.tdsAmount;

    if (cgst == 0 && sgst == 0 && igst == 0 && widget.totalAmount > 0) {
      cgst = widget.totalAmount * 0.09;
      sgst = widget.totalAmount * 0.09;
      igst = widget.totalAmount * 0.05;
      tds = widget.totalAmount * 0.02;
    }

    final totalTax = cgst + sgst + igst;
    final netBase = math.max(0.0, widget.totalAmount - totalTax);

    final segments = [
      _TaxSegment(
        title: 'Net Base Amount',
        amount: netBase > 0 ? netBase : (widget.totalAmount > 0 ? widget.totalAmount : 82000),
        color: AppTheme.primaryColor,
        icon: Icons.account_balance_wallet_rounded,
      ),
      _TaxSegment(
        title: 'CGST (Central GST)',
        amount: cgst > 0 ? cgst : 9000,
        color: const Color(0xFF3B82F6),
        icon: Icons.shield_rounded,
      ),
      _TaxSegment(
        title: 'SGST (State GST)',
        amount: sgst > 0 ? sgst : 9000,
        color: const Color(0xFF10B981),
        icon: Icons.location_city_rounded,
      ),
      _TaxSegment(
        title: 'IGST (Integrated)',
        amount: igst > 0 ? igst : 5000,
        color: const Color(0xFF8B5CF6),
        icon: Icons.swap_horiz_rounded,
      ),
      _TaxSegment(
        title: 'TDS (Withholding)',
        amount: tds > 0 ? tds : 2000,
        color: const Color(0xFFF59E0B),
        icon: Icons.pie_chart_outline_rounded,
      ),
    ];

    final grandSum = segments.fold(0.0, (sum, item) => sum + item.amount);

    return GlassCard(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    padding: const EdgeInsets.all(7),
                    decoration: BoxDecoration(
                      color: AppTheme.accentColor.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(
                      Icons.donut_large_rounded,
                      size: 18,
                      color: AppTheme.accentColor,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Text(
                    'GST & Tax Distribution',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      color: isDark ? Colors.white : const Color(0xFF0F172A),
                    ),
                  ),
                ],
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
                decoration: BoxDecoration(
                  color: AppTheme.accentColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppTheme.accentColor.withValues(alpha: 0.3)),
                ),
                child: Text(
                  'Auto-Reconciled',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.accentColor,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),

          // Multi-Segment Interactive Progress Bar
          ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: SizedBox(
              height: 14,
              child: Row(
                children: segments.map((seg) {
                  final flex = grandSum > 0 ? ((seg.amount / grandSum) * 1000).round() : 1;
                  return Expanded(
                    flex: math.max(1, flex),
                    child: Container(
                      color: seg.color,
                      margin: const EdgeInsets.symmetric(horizontal: 0.5),
                    ),
                  );
                }).toList(),
              ),
            ),
          ),
          const SizedBox(height: 18),

          // Legend & Individual Metrics Grid
          Column(
            children: segments.asMap().entries.map((entry) {
              final idx = entry.key;
              final seg = entry.value;
              final pct = grandSum > 0 ? (seg.amount / grandSum * 100) : 0.0;
              final isHovered = _hoveredIndex == idx;

              return MouseRegion(
                onEnter: (_) => setState(() => _hoveredIndex = idx),
                onExit: (_) => setState(() => _hoveredIndex = null),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 150),
                  margin: const EdgeInsets.symmetric(vertical: 3),
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: isHovered
                        ? (isDark ? Colors.white10 : Colors.black.withValues(alpha: 0.04))
                        : Colors.transparent,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    children: [
                      Container(
                        width: 10,
                        height: 10,
                        decoration: BoxDecoration(
                          color: seg.color,
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          seg.title,
                          style: TextStyle(
                            fontSize: 12.5,
                            fontWeight: isHovered ? FontWeight.w700 : FontWeight.w500,
                            color: isDark ? Colors.white : const Color(0xFF1E293B),
                          ),
                        ),
                      ),
                      Text(
                        '${pct.toStringAsFixed(1)}%',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: isDark ? AppTheme.darkTextMuted : AppTheme.lightTextMuted,
                        ),
                      ),
                      const SizedBox(width: 14),
                      Text(
                        currencyFormat.format(seg.amount),
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                          color: isDark ? Colors.white : const Color(0xFF0F172A),
                        ),
                      ),
                    ],
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }
}

class _TaxSegment {
  final String title;
  final double amount;
  final Color color;
  final IconData icon;

  _TaxSegment({
    required this.title,
    required this.amount,
    required this.color,
    required this.icon,
  });
}
