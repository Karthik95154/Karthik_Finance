import 'package:flutter/material.dart';
import '../config/theme.dart';

class AuroraBackground extends StatelessWidget {
  final Widget child;
  final bool enableAnimation;

  const AuroraBackground({
    super.key,
    required this.child,
    this.enableAnimation = true,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Stack(
      children: [
        // Clean, elegant canvas background
        Positioned.fill(
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 350),
            curve: Curves.easeInOut,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: isDark
                    ? const [
                        Color(0xFF090D16),
                        Color(0xFF0F172A),
                        Color(0xFF0B1120),
                      ]
                    : const [
                        Color(0xFFF8FAFC),
                        Color(0xFFF1F5F9),
                        Color(0xFFF8FAFC),
                      ],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
            ),
          ),
        ),

        // Very subtle top-right ambient accent glow
        Positioned(
          top: -80,
          right: -80,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 350),
            curve: Curves.easeInOut,
            width: 360,
            height: 360,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(
                colors: [
                  (isDark ? AppTheme.primaryColor : AppTheme.primaryLight)
                      .withValues(alpha: isDark ? 0.12 : 0.05),
                  Colors.transparent,
                ],
                stops: const [0.0, 0.7],
              ),
            ),
          ),
        ),

        // Very subtle bottom-left cyan tint
        Positioned(
          bottom: -100,
          left: 100,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 350),
            curve: Curves.easeInOut,
            width: 320,
            height: 320,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(
                colors: [
                  AppTheme.secondaryColor.withValues(alpha: isDark ? 0.08 : 0.03),
                  Colors.transparent,
                ],
                stops: const [0.0, 0.7],
              ),
            ),
          ),
        ),

        // Foreground Content
        Positioned.fill(
          child: child,
        ),
      ],
    );
  }
}

