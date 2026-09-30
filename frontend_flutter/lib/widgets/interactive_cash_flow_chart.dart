import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../config/theme.dart';
import 'glass_card.dart';

class InteractiveCashFlowChart extends StatefulWidget {
  final double totalAmount;
  final int totalInvoices;

  const InteractiveCashFlowChart({
    super.key,
    required this.totalAmount,
    required this.totalInvoices,
  });

  @override
  State<InteractiveCashFlowChart> createState() => _InteractiveCashFlowChartState();
}

class _InteractiveCashFlowChartState extends State<InteractiveCashFlowChart> {
  int _selectedTimeframeIndex = 1; // 0: 7D, 1: 30D, 2: 90D, 3: 1Y
  int? _hoveredPointIndex;

  final List<String> _timeframes = ['7D', '30D', '90D', '1Y'];

  List<_DataPoint> _generateDataPoints() {
    final now = DateTime.now();
    final points = <_DataPoint>[];
    final base = widget.totalAmount > 0 ? widget.totalAmount / 6 : 45000.0;

    int count = 6;
    if (_selectedTimeframeIndex == 0) count = 7;
    if (_selectedTimeframeIndex == 1) count = 6;
    if (_selectedTimeframeIndex == 2) count = 8;
    if (_selectedTimeframeIndex == 3) count = 12;

    for (int i = count - 1; i >= 0; i--) {
      DateTime date;
      String label;
      if (_selectedTimeframeIndex == 0) {
        date = now.subtract(Duration(days: i));
        label = DateFormat('E').format(date);
      } else if (_selectedTimeframeIndex == 1) {
        date = now.subtract(Duration(days: i * 5));
        label = DateFormat('d MMM').format(date);
      } else if (_selectedTimeframeIndex == 2) {
        date = now.subtract(Duration(days: i * 11));
        label = DateFormat('MMM d').format(date);
      } else {
        date = DateTime(now.year, now.month - i, 1);
        label = DateFormat('MMM').format(date);
      }

      // Generate a smooth trending financial curve
      final factor = 0.7 + (math.sin((i * 1.3) + _selectedTimeframeIndex) * 0.3) + ((count - i) * 0.05);
      final value = math.max(12000.0, base * factor);
      final taxAmount = value * 0.18;

      points.add(_DataPoint(
        label: label,
        date: date,
        amount: value,
        taxAmount: taxAmount,
        invoicesCount: math.max(1, (widget.totalInvoices / count * factor).round()),
      ));
    }
    return points;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final currencyFormat = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 0);

    final dataPoints = _generateDataPoints();
    final maxAmount = dataPoints.map((p) => p.amount).fold(0.0, math.max);

    return GlassCard(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header Row with Timeframe Selector
          Wrap(
            alignment: WrapAlignment.spaceBetween,
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 12,
            runSpacing: 8,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        padding: const EdgeInsets.all(7),
                        decoration: BoxDecoration(
                          color: AppTheme.primaryColor.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(
                          Icons.show_chart_rounded,
                          size: 18,
                          color: AppTheme.primaryLight,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Text(
                        'Cash Flow & Spend Trajectory',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                          color: isDark ? Colors.white : const Color(0xFF0F172A),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Historical processed invoice volumes & automated GST deductions',
                    style: TextStyle(
                      fontSize: 12,
                      color: isDark ? AppTheme.darkTextSecondary : AppTheme.lightTextSecondary,
                    ),
                  ),
                ],
              ),
              Container(
                decoration: BoxDecoration(
                  color: isDark ? const Color(0xFF0B132B) : const Color(0xFFE2E8F0),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: isDark ? Colors.white10 : Colors.black12,
                  ),
                ),
                padding: const EdgeInsets.all(3),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: List.generate(_timeframes.length, (index) {
                    final isSelected = _selectedTimeframeIndex == index;
                    return GestureDetector(
                      onTap: () {
                        setState(() {
                          _selectedTimeframeIndex = index;
                          _hoveredPointIndex = null;
                        });
                      },
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 200),
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
                        decoration: BoxDecoration(
                          color: isSelected
                              ? AppTheme.primaryColor
                              : Colors.transparent,
                          borderRadius: BorderRadius.circular(16),
                          boxShadow: isSelected
                              ? [
                                  BoxShadow(
                                    color: AppTheme.primaryColor.withValues(alpha: 0.35),
                                    blurRadius: 6,
                                    offset: const Offset(0, 2),
                                  ),
                                ]
                              : null,
                        ),
                        child: Text(
                          _timeframes[index],
                          style: TextStyle(
                            fontSize: 11.5,
                            fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                            color: isSelected
                                ? Colors.white
                                : (isDark ? Colors.white70 : Colors.black87),
                          ),
                        ),
                      ),
                    );
                  }),
                ),
              ),
            ],
          ),

          const SizedBox(height: 20),

          // Hover / Active Stat Preview
          if (_hoveredPointIndex != null && _hoveredPointIndex! < dataPoints.length) ...[
            Builder(builder: (context) {
              final active = dataPoints[_hoveredPointIndex!];
              return Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                margin: const EdgeInsets.only(bottom: 12),
                decoration: BoxDecoration(
                  color: isDark ? AppTheme.darkSurface : Colors.white,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(
                    color: AppTheme.primaryColor.withValues(alpha: 0.3),
                  ),
                ),
                child: Wrap(
                  spacing: 16,
                  runSpacing: 4,
                  children: [
                    Text(
                      'Period: ${active.label}',
                      style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12),
                    ),
                    Text(
                      'Volume: ${currencyFormat.format(active.amount)}',
                      style: const TextStyle(
                        fontWeight: FontWeight.w700,
                        fontSize: 12,
                        color: AppTheme.primaryLight,
                      ),
                    ),
                    Text(
                      'Tax: ${currencyFormat.format(active.taxAmount)}',
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 12,
                        color: AppTheme.secondaryColor,
                      ),
                    ),
                    Text(
                      'Invoices: ${active.invoicesCount}',
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 12,
                        color: AppTheme.accentColor,
                      ),
                    ),
                  ],
                ),
              );
            }),
          ],

          // Chart Custom Canvas
          SizedBox(
            height: 180,
            child: LayoutBuilder(
              builder: (context, constraints) {
                return GestureDetector(
                  onPanDown: (details) => _handleTouch(details.localPosition, constraints.maxWidth, dataPoints.length),
                  onPanUpdate: (details) => _handleTouch(details.localPosition, constraints.maxWidth, dataPoints.length),
                  child: CustomPaint(
                    size: Size(constraints.maxWidth, 180),
                    painter: _CashFlowPainter(
                      dataPoints: dataPoints,
                      maxAmount: maxAmount > 0 ? maxAmount * 1.15 : 100000,
                      isDark: isDark,
                      selectedIndex: _hoveredPointIndex,
                    ),
                  ),
                );
              },
            ),
          ),

          const SizedBox(height: 10),

          // X-Axis Labels
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: dataPoints.map((p) {
              return Text(
                p.label,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w500,
                  color: isDark ? AppTheme.darkTextMuted : AppTheme.lightTextMuted,
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  void _handleTouch(Offset localPosition, double width, int pointCount) {
    final step = width / (pointCount - 1);
    final index = (localPosition.dx / step).round().clamp(0, pointCount - 1);
    if (_hoveredPointIndex != index) {
      setState(() {
        _hoveredPointIndex = index;
      });
    }
  }
}

class _DataPoint {
  final String label;
  final DateTime date;
  final double amount;
  final double taxAmount;
  final int invoicesCount;

  _DataPoint({
    required this.label,
    required this.date,
    required this.amount,
    required this.taxAmount,
    required this.invoicesCount,
  });
}

class _CashFlowPainter extends CustomPainter {
  final List<_DataPoint> dataPoints;
  final double maxAmount;
  final bool isDark;
  final int? selectedIndex;

  _CashFlowPainter({
    required this.dataPoints,
    required this.maxAmount,
    required this.isDark,
    this.selectedIndex,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (dataPoints.isEmpty) return;

    final width = size.width;
    final height = size.height;
    final stepX = width / (dataPoints.length - 1);

    // Draw horizontal grid guidelines
    final gridPaint = Paint()
      ..color = (isDark ? Colors.white : Colors.black).withValues(alpha: 0.05)
      ..strokeWidth = 1;

    for (int i = 1; i <= 3; i++) {
      final y = height * (i / 4);
      canvas.drawLine(Offset(0, y), Offset(width, y), gridPaint);
    }

    // Build curve path
    final path = Path();
    final gradientPath = Path();

    final points = <Offset>[];
    for (int i = 0; i < dataPoints.length; i++) {
      final x = i * stepX;
      final normalizedY = (dataPoints[i].amount / maxAmount).clamp(0.0, 1.0);
      final y = height - (normalizedY * (height - 20)) - 10;
      points.add(Offset(x, y));
    }

    path.moveTo(points[0].dx, points[0].dy);
    gradientPath.moveTo(points[0].dx, points[0].dy);

    for (int i = 0; i < points.length - 1; i++) {
      final p0 = points[i];
      final p1 = points[i + 1];
      final controlX = (p0.dx + p1.dx) / 2;
      path.cubicTo(controlX, p0.dy, controlX, p1.dy, p1.dx, p1.dy);
      gradientPath.cubicTo(controlX, p0.dy, controlX, p1.dy, p1.dx, p1.dy);
    }

    gradientPath.lineTo(points.last.dx, height);
    gradientPath.lineTo(points.first.dx, height);
    gradientPath.close();

    // Fill Gradient
    final fillGradient = LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [
        AppTheme.primaryColor.withValues(alpha: 0.35),
        AppTheme.primaryColor.withValues(alpha: 0.02),
      ],
    );
    final fillPaint = Paint()
      ..shader = fillGradient.createShader(Rect.fromLTWH(0, 0, width, height))
      ..style = PaintingStyle.fill;
    canvas.drawPath(gradientPath, fillPaint);

    // Line Stroke with subtle glow
    final strokePaint = Paint()
      ..color = AppTheme.primaryLight
      ..strokeWidth = 3
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    canvas.drawPath(path, strokePaint);

    // Draw nodes
    for (int i = 0; i < points.length; i++) {
      final isSelected = selectedIndex == i;
      final nodePaint = Paint()
        ..color = isSelected ? Colors.white : AppTheme.primaryColor
        ..style = PaintingStyle.fill;

      final borderPaint = Paint()
        ..color = isSelected ? AppTheme.accentColor : AppTheme.primaryLight
        ..strokeWidth = isSelected ? 3 : 2
        ..style = PaintingStyle.stroke;

      if (isSelected) {
        // Glowing halo for selected point
        final haloPaint = Paint()
          ..color = AppTheme.accentColor.withValues(alpha: 0.4)
          ..style = PaintingStyle.fill;
        canvas.drawCircle(points[i], 10, haloPaint);
      }

      canvas.drawCircle(points[i], isSelected ? 6 : 4, nodePaint);
      canvas.drawCircle(points[i], isSelected ? 6 : 4, borderPaint);
    }
  }

  @override
  bool shouldRepaint(covariant _CashFlowPainter oldDelegate) {
    return oldDelegate.selectedIndex != selectedIndex ||
        oldDelegate.dataPoints != dataPoints ||
        oldDelegate.isDark != isDark;
  }
}
