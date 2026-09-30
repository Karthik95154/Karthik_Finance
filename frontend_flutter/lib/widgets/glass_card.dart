import 'dart:ui';
import 'package:flutter/material.dart';
import '../config/theme.dart';

class GlassCard extends StatefulWidget {
  final Widget child;
  final EdgeInsetsGeometry? padding;
  final EdgeInsetsGeometry? margin;
  final VoidCallback? onTap;
  final Color? borderColor;
  final Color? backgroundColor;
  final double borderRadius;
  final bool isInteractive;
  final double blur;
  final bool enableGlow;
  final Color? glowColor;

  const GlassCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(20),
    this.margin,
    this.onTap,
    this.borderColor,
    this.backgroundColor,
    this.borderRadius = 16,
    this.isInteractive = false,
    this.blur = 12,
    this.enableGlow = false,
    this.glowColor,
  });

  @override
  State<GlassCard> createState() => _GlassCardState();
}

class _GlassCardState extends State<GlassCard> {
  bool _isHovered = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    final defaultBg = isDark
        ? const Color(0xFF111827).withValues(alpha: 0.9)
        : Colors.white;

    final defaultBorder = isDark
        ? const Color(0xFF1E293B)
        : const Color(0xFFE2E8F0);

    final hoverBorder = isDark
        ? AppTheme.primaryLight.withValues(alpha: 0.6)
        : AppTheme.primaryColor.withValues(alpha: 0.4);

    return MouseRegion(
      cursor: (widget.onTap != null || widget.isInteractive)
          ? SystemMouseCursors.click
          : SystemMouseCursors.basic,
      onEnter: (_) => setState(() => _isHovered = true),
      onExit: (_) => setState(() => _isHovered = false),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOutCubic,
        margin: widget.margin,
        transform: Matrix4.translationValues(
          0,
          (_isHovered && (widget.onTap != null || widget.isInteractive)) ? -2 : 0,
          0,
        ),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(widget.borderRadius),
          boxShadow: isDark
              ? [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: _isHovered ? 0.4 : 0.25),
                    blurRadius: _isHovered ? 16 : 8,
                    offset: Offset(0, _isHovered ? 6 : 2),
                  ),
                ]
              : [
                  BoxShadow(
                    color: const Color(0xFF0F172A).withValues(alpha: _isHovered ? 0.08 : 0.05),
                    blurRadius: _isHovered ? 12 : 5,
                    offset: Offset(0, _isHovered ? 4 : 1),
                  ),
                  BoxShadow(
                    color: const Color(0xFF0F172A).withValues(alpha: _isHovered ? 0.04 : 0.02),
                    blurRadius: 2,
                    offset: const Offset(0, 1),
                  ),
                ],
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(widget.borderRadius),
          child: BackdropFilter(
            filter: ImageFilter.blur(sigmaX: widget.blur, sigmaY: widget.blur),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 300),
              curve: Curves.easeInOut,
              padding: widget.padding,
              decoration: BoxDecoration(
                color: widget.backgroundColor ?? defaultBg,
                borderRadius: BorderRadius.circular(widget.borderRadius),
                border: Border.all(
                  color: widget.borderColor ??
                      (_isHovered && (widget.onTap != null || widget.isInteractive)
                          ? hoverBorder
                          : defaultBorder),
                  width: 1,
                ),
              ),
              child: widget.onTap != null
                  ? Material(
                      color: Colors.transparent,
                      child: InkWell(
                        onTap: widget.onTap,
                        borderRadius: BorderRadius.circular(widget.borderRadius),
                        splashColor: AppTheme.primaryColor.withValues(alpha: 0.08),
                        highlightColor: AppTheme.primaryColor.withValues(alpha: 0.04),
                        child: widget.child,
                      ),
                    )
                  : widget.child,
            ),
          ),
        ),
      ),
    );
  }
}

