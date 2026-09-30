import 'package:flutter/material.dart';
import '../models/health_models.dart';
import '../models/integration_models.dart';
import '../services/integration_service.dart';

class IntegrationProvider extends ChangeNotifier {
  final IntegrationService _service = IntegrationService();

  HealthResponse? _health;
  bool _isLoadingHealth = false;

  ZohoConnectionStatus _zohoStatus = ZohoConnectionStatus();
  List<ZohoOrganization> _organizations = [];
  String _selectedDataCenter = 'in';
  EmailConfig _emailConfig = EmailConfig();
  List<EmailMessage> _inboxMessages = [];
  List<ZohoMasterAccount> _masterAccounts = [];
  List<ZohoMasterTax> _masterTaxes = [];
  List<ZohoMasterVendor> _masterVendors = [];

  bool _isLoading = false;
  bool _isLoadingMasterData = false;
  bool _isSyncingEmail = false;
  bool _isSyncingZoho = false;
  String? _errorMessage;

  HealthResponse? get health => _health;
  bool get isLoadingHealth => _isLoadingHealth;
  ZohoConnectionStatus get zohoStatus => _zohoStatus;
  List<ZohoOrganization> get organizations => _organizations;
  String get selectedDataCenter => _selectedDataCenter;
  EmailConfig get emailConfig => _emailConfig;
  List<EmailMessage> get inboxMessages => _inboxMessages;
  List<ZohoMasterAccount> get masterAccounts => _masterAccounts;
  List<ZohoMasterTax> get masterTaxes => _masterTaxes;
  List<ZohoMasterVendor> get masterVendors => _masterVendors;
  bool get isLoading => _isLoading;
  bool get isLoadingMasterData => _isLoadingMasterData;
  bool get isSyncingEmail => _isSyncingEmail;
  bool get isSyncingZoho => _isSyncingZoho;
  String? get errorMessage => _errorMessage;

  void setDataCenter(String dc) {
    _selectedDataCenter = dc;
    notifyListeners();
  }

  Future<void> fetchHealth() async {
    _isLoadingHealth = true;
    notifyListeners();
    try {
      _health = await _service.getHealth();
    } catch (_) {
      // handled inside service
    } finally {
      _isLoadingHealth = false;
      notifyListeners();
    }
  }

  Future<void> fetchOrganizations() async {
    try {
      _organizations = await _service.getZohoOrganizations();
      notifyListeners();
    } catch (_) {}
  }

  Future<bool> selectOrganization(String orgId) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();
    try {
      await _service.selectZohoOrganization(orgId);
      await fetchStatus();
      await fetchZohoMasterData();
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> fetchStatus() async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final results = await Future.wait([
        _service.getZohoStatus(),
        _service.getEmailConfig(),
        _service.getEmailInbox(),
      ]);
      _zohoStatus = results[0] as ZohoConnectionStatus;
      _emailConfig = results[1] as EmailConfig;
      _inboxMessages = results[2] as List<EmailMessage>;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<String> getZohoAuthUrl({String? accountsUrl, String? redirectUri}) async {
    String? accUrl = accountsUrl;
    if (accUrl == null || accUrl.isEmpty) {
      switch (_selectedDataCenter) {
        case 'com':
          accUrl = 'https://accounts.zoho.com';
          break;
        case 'eu':
          accUrl = 'https://accounts.zoho.eu';
          break;
        case 'au':
          accUrl = 'https://accounts.zoho.com.au';
          break;
        case 'in':
        default:
          accUrl = 'https://accounts.zoho.in';
          break;
      }
    }
    return await _service.getZohoAuthUrl(
      accountsUrl: accUrl,
      redirectUri: redirectUri,
    );
  }

  Future<void> syncZohoNow() async {
    _isSyncingZoho = true;
    _errorMessage = null;
    notifyListeners();
    try {
      await _service.syncZohoNow();
      _zohoStatus = await _service.getZohoStatus();
      await fetchZohoMasterData();
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
    } finally {
      _isSyncingZoho = false;
      notifyListeners();
    }
  }

  Future<void> fetchZohoMasterData() async {
    _isLoadingMasterData = true;
    notifyListeners();
    try {
      final data = await _service.getZohoMasterData();
      final accountsRaw = (data['accounts'] ?? data['chart_of_accounts']) as List? ?? [];
      final taxesRaw = (data['taxes'] ?? data['tax_rates']) as List? ?? [];
      final vendorsRaw = data['vendors'] as List? ?? [];

      _masterAccounts = accountsRaw
          .whereType<Map<String, dynamic>>()
          .map((e) => ZohoMasterAccount.fromJson(e))
          .toList();

      _masterTaxes = taxesRaw
          .whereType<Map<String, dynamic>>()
          .map((e) => ZohoMasterTax.fromJson(e))
          .toList();

      _masterVendors = vendorsRaw
          .whereType<Map<String, dynamic>>()
          .map((e) => ZohoMasterVendor.fromJson(e))
          .toList();
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
    } finally {
      _isLoadingMasterData = false;
      notifyListeners();
    }
  }

  Future<void> disconnectZoho() async {
    _isLoading = true;
    notifyListeners();
    try {
      await _service.disconnectZoho();
      _zohoStatus = ZohoConnectionStatus(isConnected: false);
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> saveEmailConfig(EmailConfig config) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();
    try {
      await _service.saveEmailConfig(config);
      await fetchStatus();
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> disconnectEmail() async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();
    try {
      await _service.disconnectIMAP();
      await fetchStatus();
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> syncEmailNow() async {
    _isSyncingEmail = true;
    _errorMessage = null;
    notifyListeners();
    try {
      await _service.syncEmailNow();
      _inboxMessages = await _service.getEmailInbox();
      await fetchStatus();
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
    } finally {
      _isSyncingEmail = false;
      notifyListeners();
    }
  }

  Future<void> refreshInbox() async {
    try {
      _inboxMessages = await _service.getEmailInbox();
      notifyListeners();
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
      notifyListeners();
    }
  }

  Future<List<int>> getInvoiceFileBytes(dynamic id) async {
    return await _service.getInvoiceFileBytes(id);
  }

  Future<void> processStagedDocument(dynamic id) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();
    try {
      await _service.processStagedInvoice(id);
      _inboxMessages = await _service.getEmailInbox();
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
      rethrow;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> deleteStagedDocument(dynamic id) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();
    try {
      await _service.deleteStagedInvoice(id);
      _inboxMessages = await _service.getEmailInbox();
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
      rethrow;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
}
