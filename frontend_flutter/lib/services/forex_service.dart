import 'package:dio/dio.dart';
import '../config/api_config.dart';
import '../models/forex_models.dart';
import 'api_client.dart';

class ForexService {
  final ApiClient _client = ApiClient();

  Future<ForexRatesResponse> getForexRates({String? date}) async {
    try {
      final response = await _client.get(
        ApiConfig.forexRates,
        queryParameters: date != null ? {'rate_date': date} : null,
      );
      if (response.data is Map<String, dynamic>) {
        return ForexRatesResponse.fromJson(response.data as Map<String, dynamic>);
      }
      throw Exception('Unexpected response format');
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? e.message ?? 'Failed to load exchange rates';
      throw Exception(msg);
    }
  }
}
