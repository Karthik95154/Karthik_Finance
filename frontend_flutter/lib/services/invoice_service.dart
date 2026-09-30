import 'package:dio/dio.dart';
import 'package:http_parser/http_parser.dart';
import '../config/api_config.dart';
import '../models/audit_models.dart';
import '../models/dashboard_models.dart';
import '../models/invoice_models.dart';
import 'api_client.dart';

class InvoiceService {
  final ApiClient _client = ApiClient();

  Future<List<Invoice>> getInvoices({
    String? status,
    String? search,
    int page = 1,
    int limit = 100,
  }) async {
    try {
      final query = <String, dynamic>{
        'page': page,
        'limit': limit,
      };
      if (status != null && status != 'all') {
        query['status'] = status;
      }
      if (search != null && search.isNotEmpty) {
        query['search'] = search;
      }

      final response = await _client.get(
        ApiConfig.invoices,
        queryParameters: query,
      );

      dynamic rawList;
      if (response.data is List) {
        rawList = response.data;
      } else if (response.data is Map && response.data['invoices'] != null) {
        rawList = response.data['invoices'];
      } else if (response.data is Map && response.data['items'] != null) {
        rawList = response.data['items'];
      } else {
        rawList = [];
      }

      return (rawList as List)
          .whereType<Map<String, dynamic>>()
          .map((item) => Invoice.fromJson(item))
          .toList();
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? e.message ?? 'Failed to fetch invoices');
    }
  }

  Future<Invoice> getInvoice(dynamic id) async {
    try {
      final response = await _client.get(ApiConfig.invoiceDetail(id));
      return Invoice.fromJson(response.data);
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? e.message ?? 'Failed to fetch invoice #$id');
    }
  }

  Future<Map<String, dynamic>> getInvoiceStatus(dynamic id) async {
    try {
      final response = await _client.get(ApiConfig.invoiceStatus(id));
      return response.data is Map<String, dynamic> ? response.data : {};
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? e.message ?? 'Failed to fetch invoice status');
    }
  }

  Future<List<int>> getInvoiceFileBytes(dynamic id) async {
    try {
      final response = await _client.get(
        ApiConfig.invoiceFile(id),
        options: Options(
          responseType: ResponseType.bytes,
          receiveTimeout: const Duration(seconds: 45),
          sendTimeout: const Duration(seconds: 30),
        ),
      );
      if (response.data is List<int>) {
        return response.data as List<int>;
      }
      return List<int>.from(response.data);
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? e.message ?? 'Failed to download invoice document');
    }
  }

  Future<Invoice> uploadInvoice({
    required List<int> fileBytes,
    required String filename,
  }) async {
    try {
      String ext = filename.split('.').last.toLowerCase();
      String mimeType = 'application/pdf';
      if (ext == 'png') {
        mimeType = 'image/png';
      } else if (ext == 'jpg' || ext == 'jpeg') {
        mimeType = 'image/jpeg';
      }

      final formData = FormData.fromMap({
        'file': MultipartFile.fromBytes(
          fileBytes,
          filename: filename,
          contentType: MediaType.parse(mimeType),
        ),
      });

      final response = await _client.post(
        ApiConfig.invoiceUpload,
        data: formData,
        options: Options(
          contentType: 'multipart/form-data',
        ),
      );

      return Invoice.fromJson(response.data);
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? e.message ?? 'Upload failed');
    }
  }

  Future<Invoice> updateInvoice(
    dynamic id, {
    Map<String, dynamic>? currentVlmOutput,
    Map<String, dynamic>? currentAccountingOutput,
    Map<String, dynamic>? journalEntry,
    Map<String, dynamic>? extractedData,
    Map<String, dynamic>? tdsResult,
    double? exchangeRate,
    String? fxOverrideReason,
    String? classificationOverride,
    String? classificationOverrideReason,
    String? exchangeRateDate,
    String? exchangeRateSource,
  }) async {
    try {
      final payload = <String, dynamic>{};
      if (currentVlmOutput != null) {
        payload['current_vlm_output'] = currentVlmOutput;
      } else if (extractedData != null) {
        payload['current_vlm_output'] = {'data': extractedData};
      }
      if (currentAccountingOutput != null) {
        payload['current_accounting_output'] = currentAccountingOutput;
      } else if (tdsResult != null) {
        payload['current_accounting_output'] = {'tds_assessment': tdsResult};
      }
      if (journalEntry != null) {
        payload['journal_entry'] = journalEntry;
      }
      if (exchangeRate != null) {
        payload['exchange_rate'] = exchangeRate;
      }
      if (fxOverrideReason != null && fxOverrideReason.isNotEmpty) {
        payload['fx_override_reason'] = fxOverrideReason;
      }
      if (classificationOverride != null && classificationOverride.isNotEmpty) {
        payload['classification_override'] = classificationOverride;
      }
      if (classificationOverrideReason != null && classificationOverrideReason.isNotEmpty) {
        payload['classification_override_reason'] = classificationOverrideReason;
      }
      if (exchangeRateDate != null && exchangeRateDate.isNotEmpty) {
        payload['exchange_rate_date'] = exchangeRateDate;
      }
      if (exchangeRateSource != null && exchangeRateSource.isNotEmpty) {
        payload['exchange_rate_source'] = exchangeRateSource;
      }

      final response = await _client.put(
        ApiConfig.invoiceUpdate(id),
        data: payload,
      );
      return Invoice.fromJson(response.data);
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? e.message ?? 'Failed to save invoice');
    }
  }

  // Classification Override with mandatory reason
  Future<Map<String, dynamic>> overrideClassification(
    dynamic id, {
    required String classification,
    required String reason,
  }) async {
    try {
      final response = await _client.post(
        ApiConfig.invoiceClassificationOverride(id),
        data: {
          'classification': classification.toUpperCase().trim(),
          'reason': reason.trim(),
        },
      );
      return response.data is Map<String, dynamic> ? response.data : {'status': 'success'};
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? e.message ?? 'Failed to override classification');
    }
  }

  // Master Approval
  Future<Invoice> approveInvoice(dynamic id) async {
    try {
      final response = await _client.post(ApiConfig.invoiceApprove(id));
      return Invoice.fromJson(response.data);
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? e.message ?? 'Failed to approve invoice');
    }
  }

  // Rejection with mandatory reason
  Future<Invoice> rejectInvoice(dynamic id, String reason) async {
    try {
      final response = await _client.post(
        ApiConfig.invoiceReject(id),
        data: {'reason': reason},
      );
      return Invoice.fromJson(response.data);
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? e.message ?? 'Failed to reject invoice');
    }
  }

  // Statutory TDS Approval
  Future<Map<String, dynamic>> approveTds(dynamic id) async {
    try {
      final response = await _client.post(ApiConfig.invoiceTdsApprove(id));
      return response.data is Map<String, dynamic> ? response.data : {'status': 'success'};
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? e.message ?? 'Failed to approve TDS assessment');
    }
  }

  // General Ledger Balanced Journal Approval
  Future<Map<String, dynamic>> approveJournal(dynamic id) async {
    try {
      final response = await _client.post(ApiConfig.invoiceJournalApprove(id));
      return response.data is Map<String, dynamic> ? response.data : {'status': 'success'};
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? e.message ?? 'Failed to approve Journal Entry');
    }
  }

  // Zoho Books Bill Export
  Future<Map<String, dynamic>> exportToZoho(dynamic id) async {
    try {
      final response = await _client.post(ApiConfig.invoiceExportZoho(id));
      return response.data is Map<String, dynamic> ? response.data : {'status': 'success'};
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? e.message ?? 'Zoho export failed');
    }
  }

  // Zoho Vendor Status Check on Invoice
  Future<InvoiceVendorStatusResponse> getInvoiceVendorStatus(dynamic id) async {
    try {
      final response = await _client.get(ApiConfig.invoiceVendorStatus(id));
      return InvoiceVendorStatusResponse.fromJson(response.data);
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? 'Failed to check vendor status in Zoho');
    }
  }

  // Add Vendor to Zoho Books from Invoice Details
  Future<Map<String, dynamic>> addVendorToZoho(dynamic id) async {
    try {
      final response = await _client.post(ApiConfig.invoiceAddVendorToZoho(id));
      return response.data is Map<String, dynamic> ? response.data : {'status': 'success'};
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? 'Failed to add vendor to Zoho Books');
    }
  }

  // Create Account directly in Zoho Chart of Accounts
  Future<Map<String, dynamic>> createZohoAccount({
    required String accountName,
    required String accountType,
    String? accountCode,
    String? description,
  }) async {
    try {
      final response = await _client.post(
        ApiConfig.zohoCreateCoa,
        data: {
          'account_name': accountName,
          'account_type': accountType,
          'account_code': accountCode,
          'description': description,
        },
      );
      return response.data is Map<String, dynamic> ? response.data : {'status': 'success'};
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? 'Failed to create account in Zoho COA');
    }
  }

  Future<DashboardMetrics> getDashboardMetrics() async {
    try {
      final response = await _client.get(ApiConfig.metrics);
      return DashboardMetrics.fromJson(response.data);
    } catch (_) {
      try {
        final invoices = await getInvoices(limit: 100);
        int pending = 0;
        int approved = 0;
        int exported = 0;
        int failed = 0;
        double totalAmt = 0;

        for (var inv in invoices) {
          final disp = inv.displayStatus;
          if (disp == 'exported') {
            exported++;
          } else if (disp == 'approved') {
            approved++;
          } else if (disp == 'failed') {
            failed++;
          } else {
            pending++;
          }

          if (inv.extractedData?.totalAmount != null) {
            totalAmt += inv.extractedData!.totalAmount!;
          }
        }

        return DashboardMetrics(
          totalInvoices: invoices.length,
          pendingReview: pending,
          autoApproved: approved,
          exportedZoho: exported,
          failedCount: failed,
          totalAmountProcessed: totalAmt,
        );
      } catch (_) {
        return DashboardMetrics();
      }
    }
  }

  Future<List<AuditLogEntry>> getAuditTrail(dynamic id) async {
    try {
      final response = await _client.get(ApiConfig.invoiceAuditTrail(id));
      if (response.data is List) {
        return (response.data as List)
            .whereType<Map<String, dynamic>>()
            .map((e) => AuditLogEntry.fromJson(e))
            .toList();
      }
      return [];
    } catch (_) {
      return [];
    }
  }

  Future<Map<String, dynamic>> submitPeriodDecision(dynamic id, String decision) async {
    try {
      final response = await _client.post(
        ApiConfig.invoicePeriodDecision(id),
        data: {'decision': decision.toUpperCase()},
      );
      return response.data is Map<String, dynamic> ? response.data : {'status': 'success'};
    } on DioException catch (e) {
      throw Exception(e.response?.data?['detail'] ?? 'Failed to submit accounting period decision');
    }
  }
}
