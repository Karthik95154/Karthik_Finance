import 'package:dio/dio.dart';
import '../config/api_config.dart';
import '../models/health_models.dart';
import '../models/integration_models.dart';
import 'api_client.dart';

class IntegrationService {
  final ApiClient _client = ApiClient();

  Future<HealthResponse> getHealth() async {
    try {
      final response = await _client.get(ApiConfig.health);
      return HealthResponse.fromJson(response.data);
    } catch (e) {
      return HealthResponse(
        status: 'error',
        services: {
          'backend': ServiceHealthDetail(
            name: 'FastAPI Backend',
            status: 'offline',
            statusCode: 503,
            message: e.toString(),
            endpoint: ApiConfig.baseUrl,
          ),
        },
      );
    }
  }

  Future<ZohoConnectionStatus> getZohoStatus() async {
    try {
      final response = await _client.get(ApiConfig.zohoStatus);
      return ZohoConnectionStatus.fromJson(response.data);
    } catch (_) {
      return ZohoConnectionStatus(isConnected: false, statusMessage: 'Not connected');
    }
  }

  Future<String> getZohoAuthUrl({String? accountsUrl, String? redirectUri}) async {
    try {
      final response = await _client.get(
        ApiConfig.zohoAuthUrl,
        queryParameters: {
          if (accountsUrl != null && accountsUrl.isNotEmpty) 'accounts_server': accountsUrl,
          if (redirectUri != null && redirectUri.isNotEmpty) 'redirect_uri': redirectUri,
        },
      );
      return response.data['authorization_url']?.toString() ??
          response.data['auth_url']?.toString() ??
          response.data['url']?.toString() ??
          '';
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? 'Failed to get Zoho auth URL');
    }
  }

  Future<void> disconnectZoho() async {
    try {
      await _client.post(ApiConfig.zohoDisconnect);
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? 'Failed to disconnect Zoho');
    }
  }

  Future<List<ZohoOrganization>> getZohoOrganizations() async {
    try {
      final response = await _client.get(ApiConfig.zohoOrganizations);
      final orgs = response.data['organizations'] ?? response.data;
      if (orgs is List) {
        return orgs
            .whereType<Map<String, dynamic>>()
            .map((o) => ZohoOrganization.fromJson(o))
            .toList();
      }
      return [];
    } catch (_) {
      return [];
    }
  }

  Future<void> selectZohoOrganization(String orgId, [String? orgName]) async {
    try {
      await _client.post(
        ApiConfig.zohoSelectOrg,
        data: {
          'organization_id': orgId,
          if (orgName != null) 'organization_name': orgName,
        },
      );
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? 'Failed to select Zoho organization');
    }
  }

  Future<Map<String, dynamic>> syncZohoNow() async {
    try {
      final response = await _client.post(ApiConfig.zohoSync);
      return response.data is Map<String, dynamic> ? response.data : {'status': 'success'};
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? 'Failed to sync with Zoho Books');
    }
  }

  Future<ZohoMasterDataSummary> getMasterDataSummary() async {
    try {
      final response = await _client.get(ApiConfig.zohoMasterDataSummary);
      if (response.data is Map<String, dynamic>) {
        return ZohoMasterDataSummary.fromJson(response.data);
      }
      return ZohoMasterDataSummary();
    } catch (_) {
      try {
        final fallback = await _client.get(ApiConfig.zohoMasterData);
        if (fallback.data is Map<String, dynamic>) {
          return ZohoMasterDataSummary.fromJson(fallback.data);
        }
      } catch (_) {}
      return ZohoMasterDataSummary();
    }
  }

  Future<Map<String, dynamic>> getZohoMasterData() async {
    try {
      final response = await _client.get(ApiConfig.zohoMasterData);
      return response.data is Map<String, dynamic> ? response.data : {};
    } catch (_) {
      return {};
    }
  }

  Future<EmailConfig> getEmailConfig() async {
    try {
      final response = await _client.get(ApiConfig.emailConfig);
      return EmailConfig.fromJson(response.data);
    } catch (_) {
      return EmailConfig();
    }
  }

  Future<void> saveEmailConfig(EmailConfig config) async {
    try {
      await _client.post(
        ApiConfig.emailConfigure,
        data: config.toJson(),
      );
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? 'Failed to save email config');
    }
  }

  Future<void> disconnectIMAP() async {
    try {
      await _client.post(ApiConfig.emailDisconnect);
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? 'Failed to disconnect IMAP');
    }
  }

  Future<Map<String, dynamic>> syncEmailNow() async {
    try {
      final response = await _client.post(ApiConfig.emailPoll);
      return response.data is Map<String, dynamic> ? response.data : {'status': 'success'};
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? 'Failed to sync emails');
    }
  }

  Future<List<EmailMessage>> getEmailInbox() async {
    try {
      final response = await _client.get(ApiConfig.stagedInbox);
      if (response.data is List) {
        return (response.data as List)
            .whereType<Map<String, dynamic>>()
            .map((e) => EmailMessage.fromJson(e))
            .toList();
      }
      return [];
    } catch (_) {
      return [];
    }
  }

  Future<List<int>> getInvoiceFileBytes(dynamic id) async {
    try {
      final response = await _client.get(
        ApiConfig.invoiceFile(id),
        options: Options(responseType: ResponseType.bytes),
      );
      if (response.data is List<int>) {
        return response.data as List<int>;
      }
      return List<int>.from(response.data);
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? e.message ?? 'Failed to download document');
    }
  }

  Future<Map<String, dynamic>> processStagedInvoice(dynamic id) async {
    try {
      final response = await _client.post(ApiConfig.stagedProcess(id));
      return response.data is Map<String, dynamic> ? response.data : {'success': true};
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? e.message ?? 'Failed to process staged document');
    }
  }

  Future<void> deleteStagedInvoice(dynamic id) async {
    try {
      await _client.delete(ApiConfig.stagedDelete(id));
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? e.message ?? 'Failed to delete staged document');
    }
  }
}
