import 'package:flutter/material.dart';
import '../config/theme.dart';

/// Modern shimmering animated skeleton container with smooth gradient wave
class ShimmerBox extends StatefulWidget {
  final double? width;
  final double? height;
  final double borderRadius;
  final EdgeInsetsGeometry? margin;
  final EdgeInsetsGeometry? padding;
  final Widget? child;
  final ShapeBorder? shapeBorder;

  const ShimmerBox({
    super.key,
    this.width,
    this.height,
    this.borderRadius = 8.0,
    this.margin,
    this.padding,
    this.child,
    this.shapeBorder,
  });

  const ShimmerBox.circular({
    super.key,
    required double size,
    this.margin,
    this.padding,
    this.child,
  })  : width = size,
        height = size,
        borderRadius = size / 2,
        shapeBorder = const CircleBorder();

  @override
  State<ShimmerBox> createState() => _ShimmerBoxState();
}

class _ShimmerBoxState extends State<ShimmerBox> with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    final baseColor = isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0);
    final highlightColor = isDark ? const Color(0xFF334155) : const Color(0xFFF1F5F9);

    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return Container(
          width: widget.width,
          height: widget.height,
          margin: widget.margin,
          padding: widget.padding,
          decoration: ShapeDecoration(
            shape: widget.shapeBorder ??
                RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(widget.borderRadius),
                ),
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                baseColor,
                highlightColor,
                baseColor,
              ],
              stops: [
                (_controller.value - 0.3).clamp(0.0, 1.0),
                _controller.value.clamp(0.0, 1.0),
                (_controller.value + 0.3).clamp(0.0, 1.0),
              ],
            ),
          ),
          child: widget.child,
        );
      },
      child: widget.child,
    );
  }
}

/// Full Workspace Skeleton Loading View
class WorkspaceSkeletonView extends StatelessWidget {
  final String statusMessage;

  const WorkspaceSkeletonView({
    super.key,
    this.statusMessage = 'Extracting invoice data & statutory tax schedule...',
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final isMobile = MediaQuery.of(context).size.width < 1000;

    return Scaffold(
      backgroundColor: isDark ? AppTheme.darkBg : AppTheme.lightBg,
      appBar: PreferredSize(
        preferredSize: const Size.fromHeight(64),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          decoration: BoxDecoration(
            color: isDark ? const Color(0xFF0F172A) : Colors.white,
            border: Border(
              bottom: BorderSide(
                color: isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0),
              ),
            ),
          ),
          child: Row(
            children: [
              const ShimmerBox(width: 36, height: 36, borderRadius: 8),
              const SizedBox(width: 16),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.center,
                children: const [
                  ShimmerBox(width: 180, height: 16, borderRadius: 4),
                  SizedBox(height: 6),
                  ShimmerBox(width: 120, height: 11, borderRadius: 4),
                ],
              ),
              const SizedBox(width: 12),
              const ShimmerBox(width: 90, height: 24, borderRadius: 12),
              const Spacer(),
              // Processing Banner in AppBar
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                decoration: BoxDecoration(
                  color: AppTheme.primaryColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: AppTheme.primaryColor.withValues(alpha: 0.3),
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const SizedBox(
                      width: 12,
                      height: 12,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: AppTheme.primaryColor,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      statusMessage,
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.primaryColor,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 16),
              const ShimmerBox(width: 100, height: 36, borderRadius: 8),
              const SizedBox(width: 10),
              const ShimmerBox(width: 140, height: 36, borderRadius: 8),
            ],
          ),
        ),
      ),
      body: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Left Pane: Document Viewer Skeleton (on wide screens)
          if (!isMobile)
            SizedBox(
              width: MediaQuery.of(context).size.width * 0.42,
              child: const DocumentPreviewSkeleton(),
            ),

          // Right Pane: Form & Schedule Skeleton
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Section Jump Bar Skeleton
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 10),
                  decoration: BoxDecoration(
                    color: isDark ? const Color(0xFF0B132B) : const Color(0xFFF8FAFC),
                    border: Border(
                      bottom: BorderSide(
                        color: isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0),
                      ),
                    ),
                  ),
                  child: SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(
                      children: const [
                        ShimmerBox(width: 140, height: 34, borderRadius: 8),
                        SizedBox(width: 8),
                        ShimmerBox(width: 110, height: 34, borderRadius: 8),
                        SizedBox(width: 8),
                        ShimmerBox(width: 150, height: 34, borderRadius: 8),
                        SizedBox(width: 8),
                        ShimmerBox(width: 110, height: 34, borderRadius: 8),
                        SizedBox(width: 8),
                        ShimmerBox(width: 140, height: 34, borderRadius: 8),
                      ],
                    ),
                  ),
                ),

                // Scrollable Form Skeleton
                Expanded(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 18),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Vendor Verification Banner Skeleton
                        Container(
                          padding: const EdgeInsets.all(14),
                          decoration: BoxDecoration(
                            color: isDark ? const Color(0xFF131D33) : Colors.white,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(
                              color: isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0),
                            ),
                          ),
                          child: Row(
                            children: const [
                              ShimmerBox.circular(size: 32),
                              SizedBox(width: 12),
                              Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  ShimmerBox(width: 200, height: 14, borderRadius: 4),
                                  SizedBox(height: 4),
                                  ShimmerBox(width: 140, height: 11, borderRadius: 4),
                                ],
                              ),
                              Spacer(),
                              ShimmerBox(width: 110, height: 30, borderRadius: 6),
                            ],
                          ),
                        ),
                        const SizedBox(height: 16),

                        // Header & Parties Grid Skeleton
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            // Vendor Details Card Skeleton
                            Expanded(
                              child: _buildSkeletonCard(
                                isDark: isDark,
                                titleWidth: 140,
                                rows: 4,
                              ),
                            ),
                            const SizedBox(width: 16),
                            // Invoice Details Card Skeleton
                            Expanded(
                              child: _buildSkeletonCard(
                                isDark: isDark,
                                titleWidth: 160,
                                rows: 4,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 18),

                        // Line Items Table Skeleton Card
                        Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: isDark ? const Color(0xFF131D33) : Colors.white,
                            borderRadius: BorderRadius.circular(14),
                            border: Border.all(
                              color: isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0),
                            ),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: const [
                                  ShimmerBox(width: 220, height: 18, borderRadius: 4),
                                  Spacer(),
                                  ShimmerBox(width: 90, height: 28, borderRadius: 6),
                                ],
                              ),
                              const SizedBox(height: 16),
                              // Table Header
                              const ShimmerBox(width: double.infinity, height: 40, borderRadius: 6),
                              const SizedBox(height: 8),
                              // Table Rows
                              const ShimmerBox(width: double.infinity, height: 48, borderRadius: 6),
                              const SizedBox(height: 6),
                              const ShimmerBox(width: double.infinity, height: 48, borderRadius: 6),
                              const SizedBox(height: 6),
                              const ShimmerBox(width: double.infinity, height: 48, borderRadius: 6),
                              const SizedBox(height: 14),
                              // Table Subtotal Summary Bar
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: const [
                                  ShimmerBox(width: 180, height: 20, borderRadius: 4),
                                  ShimmerBox(width: 140, height: 20, borderRadius: 4),
                                  ShimmerBox(width: 180, height: 20, borderRadius: 4),
                                ],
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 18),

                        // Financial Settlement & Tax Engine Cards Skeleton
                        Row(
                          children: [
                            Expanded(
                              child: _buildMetricSkeletonCard(isDark: isDark, label: 'Taxable Subtotal'),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: _buildMetricSkeletonCard(isDark: isDark, label: 'Total GST & CESS'),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: _buildMetricSkeletonCard(isDark: isDark, label: 'Invoice Grand Total'),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: _buildMetricSkeletonCard(isDark: isDark, label: 'Net Vendor Payable'),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  static Widget _buildSkeletonCard({
    required bool isDark,
    required double titleWidth,
    required int rows,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF131D33) : Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const ShimmerBox.circular(size: 24),
              const SizedBox(width: 8),
              ShimmerBox(width: titleWidth, height: 16, borderRadius: 4),
            ],
          ),
          const SizedBox(height: 16),
          for (int i = 0; i < rows; i++) ...[
            Row(
              children: [
                ShimmerBox(width: 80 + (i * 10), height: 12, borderRadius: 4),
                const Spacer(),
                ShimmerBox(width: 120 - (i * 5), height: 12, borderRadius: 4),
              ],
            ),
            if (i < rows - 1) const SizedBox(height: 10),
          ],
        ],
      ),
    );
  }

  static Widget _buildMetricSkeletonCard({
    required bool isDark,
    required String label,
  }) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF131D33) : Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: isDark ? const Color(0xFF64748B) : const Color(0xFF94A3B8),
            ),
          ),
          const SizedBox(height: 8),
          const ShimmerBox(width: 100, height: 20, borderRadius: 4),
        ],
      ),
    );
  }
}

/// Document Preview Pane Skeleton
class DocumentPreviewSkeleton extends StatelessWidget {
  const DocumentPreviewSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Container(
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF0F172A) : const Color(0xFFF8FAFC),
        border: Border(
          right: BorderSide(
            color: isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0),
          ),
        ),
      ),
      child: Column(
        children: [
          // PDF Toolbar Skeleton
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            decoration: BoxDecoration(
              color: isDark ? const Color(0xFF1E293B) : const Color(0xFFF1F5F9),
              border: Border(
                bottom: BorderSide(
                  color: isDark ? const Color(0xFF334155) : const Color(0xFFCBD5E1),
                ),
              ),
            ),
            child: Row(
              children: const [
                ShimmerBox(width: 140, height: 20, borderRadius: 4),
                Spacer(),
                ShimmerBox(width: 28, height: 28, borderRadius: 6),
                SizedBox(width: 6),
                ShimmerBox(width: 28, height: 28, borderRadius: 6),
                SizedBox(width: 6),
                ShimmerBox(width: 28, height: 28, borderRadius: 6),
                SizedBox(width: 6),
                ShimmerBox(width: 28, height: 28, borderRadius: 6),
              ],
            ),
          ),
          // PDF Canvas Preview Skeleton
          Expanded(
            child: Center(
              child: Container(
                width: double.infinity,
                margin: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: isDark ? const Color(0xFF1E293B) : Colors.white,
                  borderRadius: BorderRadius.circular(12),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.1),
                      blurRadius: 16,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: Padding(
                  padding: const EdgeInsets.all(28),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: const [
                          ShimmerBox(width: 160, height: 32, borderRadius: 6),
                          ShimmerBox(width: 60, height: 60, borderRadius: 30),
                        ],
                      ),
                      const SizedBox(height: 24),
                      const ShimmerBox(width: 220, height: 14, borderRadius: 4),
                      const SizedBox(height: 8),
                      const ShimmerBox(width: 180, height: 12, borderRadius: 4),
                      const SizedBox(height: 32),
                      // Mock Table in PDF
                      const ShimmerBox(width: double.infinity, height: 36, borderRadius: 4),
                      const SizedBox(height: 8),
                      const ShimmerBox(width: double.infinity, height: 28, borderRadius: 4),
                      const SizedBox(height: 8),
                      const ShimmerBox(width: double.infinity, height: 28, borderRadius: 4),
                      const Spacer(),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.end,
                        children: const [
                          ShimmerBox(width: 160, height: 24, borderRadius: 4),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Skeleton for List Items / Cards in Inbox & Invoices screen
class ListItemSkeleton extends StatelessWidget {
  const ListItemSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF131D33) : Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const ShimmerBox(width: 44, height: 44, borderRadius: 10),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: const [
                ShimmerBox(width: 220, height: 15, borderRadius: 4),
                SizedBox(height: 6),
                ShimmerBox(width: 160, height: 12, borderRadius: 4),
                SizedBox(height: 6),
                ShimmerBox(width: 260, height: 11, borderRadius: 4),
              ],
            ),
          ),
          const SizedBox(width: 14),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: const [
              ShimmerBox(width: 80, height: 24, borderRadius: 12),
              SizedBox(height: 8),
              ShimmerBox(width: 100, height: 32, borderRadius: 8),
            ],
          ),
        ],
      ),
    );
  }
}

/// Audit Trail Skeleton View
class AuditTrailSkeleton extends StatelessWidget {
  const AuditTrailSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF131D33) : Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: const [
              ShimmerBox.circular(size: 32),
              SizedBox(width: 12),
              ShimmerBox(width: 180, height: 18, borderRadius: 4),
            ],
          ),
          const SizedBox(height: 24),
          for (int i = 0; i < 4; i++) ...[
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const ShimmerBox.circular(size: 16),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: const [
                      ShimmerBox(width: 160, height: 14, borderRadius: 4),
                      SizedBox(height: 4),
                      ShimmerBox(width: 280, height: 11, borderRadius: 4),
                    ],
                  ),
                ),
                const ShimmerBox(width: 80, height: 12, borderRadius: 4),
              ],
            ),
            if (i < 3) const Padding(padding: EdgeInsets.symmetric(vertical: 12), child: Divider(height: 1)),
          ],
        ],
      ),
    );
  }
}

/// Integration Master Data (COA, Taxes, Contacts) Skeleton
class IntegrationMasterDataSkeleton extends StatelessWidget {
  const IntegrationMasterDataSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    return ListView.separated(
      itemCount: 8,
      separatorBuilder: (context, index) => const Divider(height: 1),
      itemBuilder: (context, index) {
        return Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: Row(
            children: const [
              ShimmerBox(width: 32, height: 32, borderRadius: 8),
              SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    ShimmerBox(width: 180, height: 14, borderRadius: 4),
                    SizedBox(height: 4),
                    ShimmerBox(width: 120, height: 11, borderRadius: 4),
                  ],
                ),
              ),
              ShimmerBox(width: 70, height: 22, borderRadius: 10),
            ],
          ),
        );
      },
    );
  }
}
