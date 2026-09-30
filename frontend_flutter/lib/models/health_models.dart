class ServiceHealthDetail {
  final String name;
  final String status;
  final int? statusCode;
  final String? message;
  final double? latencyMs;
  final String? endpoint;

  ServiceHealthDetail({
    required this.name,
    required this.status,
    this.statusCode,
    this.message,
    this.latencyMs,
    this.endpoint,
  });

  bool get isHealthy {
    final s = status.toLowerCase();
    return s == 'online' || s == 'connected' || s == 'ok' || s == 'healthy' || statusCode == 200;
  }

  factory ServiceHealthDetail.fromJson(Map<String, dynamic> json) {
    return ServiceHealthDetail(
      name: json['name']?.toString() ?? 'Service',
      status: json['status']?.toString() ?? 'offline',
      statusCode: json['status_code'] is int ? json['status_code'] : int.tryParse(json['status_code']?.toString() ?? ''),
      message: json['message']?.toString(),
      latencyMs: json['latency_ms'] is num ? (json['latency_ms'] as num).toDouble() : double.tryParse(json['latency_ms']?.toString() ?? ''),
      endpoint: json['endpoint']?.toString(),
    );
  }
}

class HealthResponse {
  final String status;
  final String? timestamp;
  final String? version;
  final Map<String, ServiceHealthDetail> services;

  HealthResponse({
    required this.status,
    this.timestamp,
    this.version,
    this.services = const {},
  });

  bool get isHealthy => status.toLowerCase() == 'healthy' || status.toLowerCase() == 'ok';

  factory HealthResponse.fromJson(Map<String, dynamic> json) {
    final sMap = <String, ServiceHealthDetail>{};
    if (json['services'] != null && json['services'] is Map<String, dynamic>) {
      (json['services'] as Map<String, dynamic>).forEach((k, v) {
        if (v is Map<String, dynamic>) {
          sMap[k] = ServiceHealthDetail.fromJson(v);
        }
      });
    }

    return HealthResponse(
      status: json['status']?.toString() ?? 'unknown',
      timestamp: json['timestamp']?.toString(),
      version: json['version']?.toString(),
      services: sMap,
    );
  }
}
