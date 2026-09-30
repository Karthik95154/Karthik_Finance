class DashboardMetrics {
  final int totalInvoices;
  final int pendingReview;
  final int autoApproved;
  final int exportedZoho;
  final int failedCount;
  final double totalAmountProcessed;
  final double averageConfidence;
  final double successRate;

  DashboardMetrics({
    this.totalInvoices = 0,
    this.pendingReview = 0,
    this.autoApproved = 0,
    this.exportedZoho = 0,
    this.failedCount = 0,
    this.totalAmountProcessed = 0.0,
    this.averageConfidence = 0.0,
    this.successRate = 0.0,
  });

  static double _toDouble(dynamic val) {
    if (val == null) return 0.0;
    if (val is num) return val.toDouble();
    if (val is String) return double.tryParse(val) ?? 0.0;
    return 0.0;
  }

  static int _toInt(dynamic val) {
    if (val == null) return 0;
    if (val is int) return val;
    if (val is num) return val.toInt();
    if (val is String) return int.tryParse(val) ?? 0;
    return 0;
  }

  factory DashboardMetrics.fromJson(Map<String, dynamic> json) {
    final total = _toInt(json['total_invoices'] ?? json['total']);
    final pending = _toInt(json['pending_review'] ?? json['pending']);
    final approved = _toInt(json['auto_approved'] ?? json['approved']);
    final exported = _toInt(json['exported_zoho'] ?? json['exported']);
    final failed = _toInt(json['failed_count'] ?? json['failed']);

    final sRate = total > 0 ? ((approved + exported) / total) * 100 : 0.0;

    return DashboardMetrics(
      totalInvoices: total,
      pendingReview: pending,
      autoApproved: approved,
      exportedZoho: exported,
      failedCount: failed,
      totalAmountProcessed: _toDouble(json['total_amount_processed'] ?? json['total_amount']),
      averageConfidence: _toDouble(json['average_confidence'] ?? json['avg_confidence']),
      successRate: json['success_rate'] != null ? _toDouble(json['success_rate']) : sRate,
    );
  }
}
