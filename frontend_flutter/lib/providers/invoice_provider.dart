import 'package:flutter/material.dart';
import '../models/audit_models.dart';
import '../models/dashboard_models.dart';
import '../models/invoice_models.dart';
import '../services/invoice_service.dart';

class InvoiceProvider extends ChangeNotifier {
  final InvoiceService _service = InvoiceService();

  List<Invoice> _invoices = [];
  DashboardMetrics _metrics = DashboardMetrics();
  Invoice? _activeInvoice;
  ExtractedInvoiceData? _editableData;
  TdsResult? _editableTds;
  ItcResult? _editableItc;
  GstResult? _editableGst;
  JournalEntry? _editableJournal;
  InvoiceVendorStatusResponse? _vendorStatus;

  bool _isLoading = false;
  bool _isSaving = false;
  bool _isApproving = false;
  bool _isRejecting = false;
  bool _isExporting = false;
  bool _isCheckingVendor = false;
  bool _isAddingVendor = false;
  bool? _isInterStateOverride;
  String? _errorMessage;
  String _selectedStatus = 'all';
  String _selectedOrigin = 'all'; // 'all', 'indian', 'foreign'
  String _searchQuery = '';

  List<Invoice> get invoices => _invoices;
  DashboardMetrics get metrics => _metrics;
  Invoice? get activeInvoice => _activeInvoice;
  ExtractedInvoiceData? get editableData => _editableData;
  TdsResult? get editableTds => _editableTds;
  ItcResult? get editableItc => _editableItc;
  GstResult? get editableGst => _editableGst;
  JournalEntry? get editableJournal => _editableJournal;
  InvoiceVendorStatusResponse? get vendorStatus => _vendorStatus;

  bool get isLoading => _isLoading;
  bool get isSaving => _isSaving;
  bool get isApproving => _isApproving;
  bool get isRejecting => _isRejecting;
  bool get isExporting => _isExporting;
  bool get isCheckingVendor => _isCheckingVendor;
  bool get isAddingVendor => _isAddingVendor;
  String? get errorMessage => _errorMessage;
  String get selectedStatus => _selectedStatus;
  String get selectedOrigin => _selectedOrigin;
  String get searchQuery => _searchQuery;

  void setOriginFilter(String origin) {
    _selectedOrigin = origin;
    notifyListeners();
  }

  bool get isInterState {
    if (_isInterStateOverride != null) return _isInterStateOverride!;
    if ((_editableData?.igstAmount ?? 0) > 0) return true;
    if ((_editableData?.cgstAmount ?? 0) > 0 || (_editableData?.sgstAmount ?? 0) > 0) return false;
    final vendorState = _editableData?.vendorGstin != null && _editableData!.vendorGstin!.length >= 2
        ? _editableData!.vendorGstin!.substring(0, 2)
        : '';
    final custState = _editableData?.customerGstin != null && _editableData!.customerGstin!.length >= 2
        ? _editableData!.customerGstin!.substring(0, 2)
        : '';
    return (vendorState.isNotEmpty && custState.isNotEmpty && vendorState != custState);
  }

  List<Invoice> get filteredInvoices {
    return _invoices.where((inv) {
      if (_selectedOrigin == 'indian' && !inv.isIndian) return false;
      if (_selectedOrigin == 'foreign' && !inv.isForeign) return false;

      if (_selectedStatus != 'all') {
        final disp = inv.displayStatus;
        if (_selectedStatus == 'pending') {
          if (disp != 'pending' && disp != 'processing') return false;
        } else if (_selectedStatus == 'approved') {
          if (disp != 'approved') return false;
        } else if (_selectedStatus == 'exported') {
          if (disp != 'exported') return false;
        } else if (_selectedStatus == 'failed') {
          if (disp != 'failed') return false;
        }
      }

      if (_searchQuery.isNotEmpty) {
        final query = _searchQuery.toLowerCase();
        final invNum = inv.extractedData?.invoiceNumber?.toLowerCase() ?? '';
        final vendor = inv.extractedData?.vendorName?.toLowerCase() ?? '';
        final filename = inv.originalFilename?.toLowerCase() ?? inv.filename?.toLowerCase() ?? '';
        final gstin = inv.extractedData?.vendorGstin?.toLowerCase() ?? '';
        final idStr = inv.id.toString().toLowerCase();

        if (!invNum.contains(query) &&
            !vendor.contains(query) &&
            !filename.contains(query) &&
            !gstin.contains(query) &&
            !idStr.contains(query)) {
          return false;
        }
      }
      return true;
    }).toList();
  }

  Future<void> fetchDashboardData() async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final results = await Future.wait([
        _service.getDashboardMetrics(),
        _service.getInvoices(limit: 100),
      ]);
      _metrics = results[0] as DashboardMetrics;
      _invoices = results[1] as List<Invoice>;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> fetchInvoices({String? status, String? search}) async {
    _isLoading = true;
    _errorMessage = null;
    if (status != null) _selectedStatus = status;
    if (search != null) _searchQuery = search;
    notifyListeners();

    try {
      _invoices = await _service.getInvoices(
        status: _selectedStatus,
        search: _searchQuery,
      );
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  void setFilterStatus(String status) {
    _selectedStatus = status;
    notifyListeners();
  }

  void setSearchQuery(String query) {
    _searchQuery = query;
    notifyListeners();
  }

  Future<Invoice> getInvoice(dynamic id) async {
    return await _service.getInvoice(id);
  }

  Future<void> loadInvoiceDetail(dynamic id, {bool silent = false}) async {
    if (!silent) {
      _isLoading = true;
      _errorMessage = null;
      notifyListeners();
    }

    try {
      _activeInvoice = await _service.getInvoice(id);
      _cloneEditableState();
      checkVendorStatus(id);
    } catch (e) {
      if (!silent) {
        _errorMessage = e.toString().replaceAll('Exception: ', '');
      }
    } finally {
      if (!silent) {
        _isLoading = false;
      }
      notifyListeners();
    }
  }

  Future<void> checkVendorStatus(dynamic id) async {
    _isCheckingVendor = true;
    notifyListeners();
    try {
      _vendorStatus = await _service.getInvoiceVendorStatus(id);
    } catch (_) {
      _vendorStatus = null;
    } finally {
      _isCheckingVendor = false;
      notifyListeners();
    }
  }

  Future<bool> addVendorToZoho() async {
    if (_activeInvoice == null) return false;
    _isAddingVendor = true;
    _errorMessage = null;
    notifyListeners();

    try {
      await _service.addVendorToZoho(_activeInvoice!.id);
      await checkVendorStatus(_activeInvoice!.id);
      _isAddingVendor = false;
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
      _isAddingVendor = false;
      notifyListeners();
      return false;
    }
  }

  Future<bool> createZohoAccount({
    required String accountName,
    required String accountType,
    String? accountCode,
    String? description,
  }) async {
    _errorMessage = null;
    try {
      await _service.createZohoAccount(
        accountName: accountName,
        accountType: accountType,
        accountCode: accountCode,
        description: description,
      );
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
      notifyListeners();
      return false;
    }
  }

  void _cloneEditableState() {
    _isJournalCustomized = false;
    _isInterStateOverride = null;
    if (_activeInvoice?.extractedData != null) {
      _editableData = ExtractedInvoiceData.fromJson(_activeInvoice!.extractedData!.toJson());
    } else {
      _editableData = ExtractedInvoiceData();
    }

    if (_activeInvoice?.tdsResult != null) {
      _editableTds = TdsResult.fromJson(_activeInvoice!.tdsResult!.toJson());
    } else {
      _editableTds = TdsResult();
    }

    if (_activeInvoice?.itcResult != null) {
      _editableItc = ItcResult.fromJson(_activeInvoice!.itcResult!.toJson());
    } else {
      _editableItc = ItcResult(
        status: 'ELIGIBLE',
        eligibleAmount: _editableData?.taxTotal ?? 0.0,
        ineligibleAmount: 0.0,
        netItcAvailable: _editableData?.taxTotal ?? 0.0,
        totalTaxAmount: _editableData?.taxTotal ?? 0.0,
      );
    }

    if (_activeInvoice?.gstResult != null) {
      _editableGst = _activeInvoice!.gstResult;
    }

    // Automatically set applicable if threshold exceeded or TDS proposed
    if (_editableTds!.applicable == null) {
      if (_editableTds!.tdsApplicable != null) {
        _editableTds!.applicable = _editableTds!.tdsApplicable;
      } else if ((_editableTds!.proposedTdsAmount ?? 0.0) > 0 ||
          (_editableTds!.tdsAmount ?? 0.0) > 0 ||
          _editableTds!.thresholdExceeded == true ||
          ((_editableTds!.projectedYtd ?? 0.0) >= (_editableTds!.thresholdLimit ?? 100000.0))) {
        _editableTds!.applicable = true;
      } else {
        _editableTds!.applicable = false;
      }
    }

    final isForeign = _activeInvoice?.isForeignService == true || _activeInvoice?.invoiceOrigin == 'FOREIGN_SERVICE';
    if (_editableTds!.applicable == true && (_editableTds!.tdsAmount == null || _editableTds!.tdsAmount == 0.0 || (_editableTds!.tdsAmount! > (_editableData?.taxableAmount ?? 0.0)))) {
      final base = _editableData?.taxableAmount ?? 0.0;
      final rate = _editableTds!.tdsRate ?? (isForeign ? 20.0 : 10.0);
      _editableTds!.tdsRate = rate;
      _editableTds!.tdsBaseAmount = base;
      _editableTds!.tdsAmount = double.parse((base * (rate / 100)).toStringAsFixed(2));
    }

    if (_editableTds!.isRcm == false && _activeInvoice?.gstResult?.isReverseCharge == true) {
      _editableTds!.isRcm = true;
    }

    if (_activeInvoice?.journalEntry != null && _activeInvoice!.journalEntry!.lines.isNotEmpty) {
      _editableJournal = JournalEntry.fromJson(_activeInvoice!.journalEntry!.toJson());
    } else {
      _editableJournal = JournalEntry();
      _recalculateJournal();
    }
  }

  void setActiveInvoice(Invoice invoice) {
    _activeInvoice = invoice;
    _cloneEditableState();
    notifyListeners();
  }

  void updateFinancialSummary({
    double? taxableAmount,
    double? cgstAmount,
    double? sgstAmount,
    double? igstAmount,
    double? cessAmount,
    double? taxTotal,
    double? discountTotal,
    double? shippingCharges,
    double? otherCharges,
    double? adjustment,
    double? roundOff,
    double? totalAmount,
    bool autoRecalcJournal = true,
  }) {
    if (_editableData == null) return;
    if (taxableAmount != null) _editableData!.taxableAmount = taxableAmount;
    if (cgstAmount != null) {
      _editableData!.cgstAmount = cgstAmount;
      if (cgstAmount > 0) _isInterStateOverride = false;
    }
    if (sgstAmount != null) {
      _editableData!.sgstAmount = sgstAmount;
      if (sgstAmount > 0) _isInterStateOverride = false;
    }
    if (igstAmount != null) {
      _editableData!.igstAmount = igstAmount;
      if (igstAmount > 0) _isInterStateOverride = true;
    }
    if (cessAmount != null) _editableData!.cessAmount = cessAmount;
    if (taxTotal != null) _editableData!.taxTotal = taxTotal;
    if (discountTotal != null) _editableData!.discountTotal = discountTotal;
    if (shippingCharges != null) _editableData!.shippingCharges = shippingCharges;
    if (otherCharges != null) _editableData!.otherCharges = otherCharges;
    if (adjustment != null) _editableData!.adjustment = adjustment;
    if (roundOff != null) _editableData!.roundOff = roundOff;
    if (totalAmount != null) _editableData!.totalAmount = totalAmount;

    if (autoRecalcJournal) {
      _recalculateJournal();
    }
    notifyListeners();
  }

  void toggleTaxSupplyType({bool? targetInterState}) {
    final nextInterState = targetInterState ?? !isInterState;
    _isInterStateOverride = nextInterState;

    if (_editableData != null) {
      for (var item in _editableData!.lineItems) {
        final rate = (item.gstRate != null && item.gstRate! > 0)
            ? item.gstRate!
            : ((item.igstRate ?? 0) > 0
                ? item.igstRate!
                : ((item.cgstRate ?? 0) + (item.sgstRate ?? 0) > 0
                    ? (item.cgstRate ?? 0) + (item.sgstRate ?? 0)
                    : 18.0));
        item.gstRate = rate;

        final qty = item.quantity ?? 1.0;
        final price = item.unitPrice ?? item.rate ?? 0.0;
        final discount = item.discount ?? 0.0;
        final lineTaxable = (item.taxableAmount != null && item.taxableAmount! > 0)
            ? item.taxableAmount!
            : ((qty * price) - discount > 0 ? (qty * price) - discount : 0.0);

        if (nextInterState) {
          item.igstRate = rate;
          item.igstAmount = lineTaxable * (rate / 100);
          item.cgstRate = 0.0;
          item.cgstAmount = 0.0;
          item.sgstRate = 0.0;
          item.sgstAmount = 0.0;
        } else {
          final half = rate / 2;
          item.cgstRate = half;
          item.sgstRate = half;
          item.cgstAmount = lineTaxable * (half / 100);
          item.sgstAmount = lineTaxable * (half / 100);
          item.igstRate = 0.0;
          item.igstAmount = 0.0;
        }
      }
    }
    _recalculateTotals();
    notifyListeners();
  }

  void updateItc({
    String? status,
    double? eligibleAmount,
    double? ineligibleAmount,
    double? netItcAvailable,
    double? totalTaxAmount,
    String? reason,
    String? ruleReference,
  }) {
    _editableItc ??= ItcResult(status: 'ELIGIBLE');
    if (status != null) _editableItc!.status = status;
    if (eligibleAmount != null) _editableItc!.eligibleAmount = eligibleAmount;
    if (ineligibleAmount != null) _editableItc!.ineligibleAmount = ineligibleAmount;
    if (netItcAvailable != null) _editableItc!.netItcAvailable = netItcAvailable;
    if (totalTaxAmount != null) _editableItc!.totalTaxAmount = totalTaxAmount;
    if (reason != null) _editableItc!.reason = reason;
    if (ruleReference != null) _editableItc!.ruleReference = ruleReference;
    notifyListeners();
  }

  void updateGst({
    String? placeOfSupply,
  }) {
    if (_editableData != null && placeOfSupply != null) {
      _editableData!.placeOfSupply = placeOfSupply;
    }
    notifyListeners();
  }

  void updateLineItem(int index, LineItem updated) {
    if (_editableData == null || index < 0 || index >= _editableData!.lineItems.length) return;
    _editableData!.lineItems[index] = updated;
    _recalculateTotals(recomputeLineTaxes: true, updateSummaryTotals: true);
    notifyListeners();
  }

  void addLineItem() {
    if (_editableData == null) return;
    _editableData!.lineItems.add(
      LineItem(
        lineIndex: _editableData!.lineItems.length + 1,
        description: 'New Item',
        quantity: 1.0,
        unitPrice: 0.0,
        taxableAmount: 0.0,
        gstRate: 18.0,
        total: 0.0,
      ),
    );
    _recalculateTotals(recomputeLineTaxes: true, updateSummaryTotals: true);
    notifyListeners();
  }

  void removeLineItem(int index) {
    if (_editableData == null || index < 0 || index >= _editableData!.lineItems.length) return;
    _editableData!.lineItems.removeAt(index);
    _recalculateTotals(recomputeLineTaxes: true, updateSummaryTotals: true);
    notifyListeners();
  }

  void updateTds({
    bool? applicable,
    String? section,
    double? rate,
    double? statutoryRate,
    double? tdsBaseAmount,
    double? tdsAmount,
    String? reason,
    String? vendorPan,
    double? previousYtd,
    bool? isRcm,
  }) {
    _editableTds ??= TdsResult();
    if (applicable != null) _editableTds!.applicable = applicable;
    if (section != null) _editableTds!.tdsSection = section;
    if (rate != null) _editableTds!.tdsRate = rate;
    if (statutoryRate != null) _editableTds!.statutoryRate = statutoryRate;
    if (isRcm != null) _editableTds!.isRcm = isRcm;
    if (reason != null) _editableTds!.reason = reason;
    if (previousYtd != null) _editableTds!.previousYtd = previousYtd;

    if (vendorPan != null && _editableData != null) {
      _editableData!.vendorPan = vendorPan;
    }

    if (tdsBaseAmount != null) {
      _editableTds!.tdsBaseAmount = tdsBaseAmount;
    } else if (_editableTds!.tdsBaseAmount == null || _editableTds!.tdsBaseAmount == 0.0) {
      _editableTds!.tdsBaseAmount = _editableData?.taxableAmount ?? 0.0;
    }

    if (tdsAmount != null) {
      _editableTds!.tdsAmount = tdsAmount;
    } else {
      final base = _editableTds!.tdsBaseAmount ?? (_editableData?.taxableAmount ?? 0.0);
      final effRate = _editableTds!.tdsRate ?? 0.0;
      _editableTds!.tdsAmount = (_editableTds!.applicable == true)
          ? (base * (effRate / 100))
          : 0.0;
    }

    _recalculateJournal();
    notifyListeners();
  }

  bool _isJournalCustomized = false;
  bool get isJournalCustomized => _isJournalCustomized;

  void updateJournalLine(int index, JournalLine updated) {
    if (_editableJournal == null || index < 0 || index >= _editableJournal!.lines.length) return;
    _editableJournal!.lines[index] = updated;
    _isJournalCustomized = true;
    _recalculateJournalTotals();
    notifyListeners();
  }

  void addJournalLine([JournalLine? customLine]) {
    _editableJournal ??= JournalEntry(
      journalNumber: 'JRN-${_activeInvoice?.id ?? 0}',
      date: _editableData?.invoiceDate ?? DateTime.now().toIso8601String().split('T').first,
      referenceNumber: _editableData?.invoiceNumber,
    );
    _editableJournal!.lines.add(
      customLine ??
          JournalLine(
            accountCode: 'EXP-ADJ',
            accountName: 'Operating Expense / Adjustment',
            debit: 0.0,
            credit: 0.0,
            provenance: 'HITL_OVERRIDE',
          ),
    );
    _isJournalCustomized = true;
    _recalculateJournalTotals();
    notifyListeners();
  }

  void removeJournalLine(int index) {
    if (_editableJournal == null || index < 0 || index >= _editableJournal!.lines.length) return;
    _editableJournal!.lines.removeAt(index);
    _isJournalCustomized = true;
    _recalculateJournalTotals();
    notifyListeners();
  }

  void resetJournalToAuto() {
    _isJournalCustomized = false;
    if (_editableTds != null && _editableData != null) {
      final taxable = _editableData!.taxableAmount ?? 0.0;
      final isForeign = _activeInvoice?.isForeignService == true || _activeInvoice?.invoiceOrigin == 'FOREIGN_SERVICE';
      if (taxable > 0 && ((_editableTds!.tdsAmount ?? 0.0) > taxable || _editableTds!.tdsAmount == 0.0)) {
        final rate = _editableTds!.tdsRate ?? (isForeign ? 20.0 : 10.0);
        _editableTds!.tdsRate = rate;
        _editableTds!.tdsBaseAmount = taxable;
        _editableTds!.tdsAmount = double.parse((taxable * (rate / 100)).toStringAsFixed(2));
      }
    }
    _recalculateJournal(force: true);
    notifyListeners();
  }

  void _recalculateJournalTotals() {
    if (_editableJournal == null) return;
    double d = 0;
    double c = 0;
    for (var l in _editableJournal!.lines) {
      d += l.debit;
      c += l.credit;
    }
    _editableJournal!.totalDebit = d;
    _editableJournal!.totalCredit = c;
    _editableJournal!.difference = (d - c).abs();
    _editableJournal!.isBalanced = _editableJournal!.difference < 0.05;
  }

  void _recalculateTotals({bool recomputeLineTaxes = false, bool updateSummaryTotals = false}) {
    if (_editableData == null) return;
    double taxable = 0.0;
    double cgst = 0.0;
    double sgst = 0.0;
    double igst = 0.0;
    double cess = 0.0;

    final effectiveInterState = isInterState;

    for (var item in _editableData!.lineItems) {
      final qty = item.quantity ?? 1.0;
      var price = item.unitPrice ?? item.rate ?? 0.0;
      final discount = item.discount ?? 0.0;

      if (price == 0.0 && item.taxableAmount != null && item.taxableAmount! > 0) {
        price = (item.taxableAmount! + discount) / (qty > 0 ? qty : 1.0);
        item.unitPrice = price;
        item.rate = price;
      }

      var lineTaxable = (item.taxableAmount != null && item.taxableAmount! > 0 && !recomputeLineTaxes)
          ? item.taxableAmount!
          : ((qty * price) - discount);
      if (lineTaxable < 0) lineTaxable = 0.0;
      if (item.taxableAmount == null || item.taxableAmount == 0.0 || recomputeLineTaxes) {
        item.taxableAmount = lineTaxable;
      }

      final rate = (item.gstRate != null && item.gstRate! > 0)
          ? item.gstRate!
          : ((item.igstRate ?? 0) > 0
              ? item.igstRate!
              : ((item.cgstRate ?? 0) + (item.sgstRate ?? 0) > 0
                  ? (item.cgstRate ?? 0) + (item.sgstRate ?? 0)
                  : 18.0));
      item.gstRate = rate;

      if (recomputeLineTaxes) {
        if (effectiveInterState) {
          final amt = lineTaxable * (rate / 100);
          item.igstRate = rate;
          item.igstAmount = amt;
          item.cgstRate = 0.0;
          item.cgstAmount = 0.0;
          item.sgstRate = 0.0;
          item.sgstAmount = 0.0;
        } else {
          final half = rate / 2;
          item.cgstRate = half;
          item.sgstRate = half;
          item.igstRate = 0.0;
          item.igstAmount = 0.0;
          final cAmt = lineTaxable * (half / 100);
          item.cgstAmount = cAmt;
          item.sgstAmount = cAmt;
        }
      }

      final lCgst = item.cgstAmount ?? 0.0;
      final lSgst = item.sgstAmount ?? 0.0;
      final lIgst = item.igstAmount ?? 0.0;
      final lCess = item.cessAmount ?? 0.0;

      cgst += lCgst;
      sgst += lSgst;
      igst += lIgst;
      cess += lCess;

      if (item.total == null || item.total == 0.0 || recomputeLineTaxes) {
        item.total = lineTaxable + lCgst + lSgst + lIgst + lCess;
      }
      taxable += (item.taxableAmount ?? lineTaxable);
    }

    if (updateSummaryTotals) {
      _editableData!.taxableAmount = taxable;
      _editableData!.cgstAmount = cgst;
      _editableData!.sgstAmount = sgst;
      _editableData!.igstAmount = igst;
      _editableData!.cessAmount = cess;
      _editableData!.taxTotal = cgst + sgst + igst + cess;
      
      final disc = _editableData!.discountTotal ?? 0.0;
      final ship = _editableData!.shippingCharges ?? 0.0;
      final other = _editableData!.otherCharges ?? 0.0;
      final adj = _editableData!.adjustment ?? 0.0;
      final ro = _editableData!.roundOff ?? 0.0;
      _editableData!.totalAmount = taxable + cgst + sgst + igst + cess - disc + ship + other + adj + ro;
    }

    if (_editableTds != null) {
      final baseTaxable = _editableData!.taxableAmount ?? taxable;
      _editableTds!.tdsBaseAmount = baseTaxable;
      if (_editableTds!.applicable == true) {
        final rate = _editableTds!.tdsRate ?? 10.0;
        _editableTds!.tdsAmount = baseTaxable * (rate / 100);
      } else {
        _editableTds!.tdsAmount = 0.0;
      }
    }

    _recalculateJournal();
  }

  /// Explicitly applies confirmed Total Auto-Fix
  void applyConfirmedTotalFix(double confirmedTotalAmount) {
    if (_editableData == null) return;
    _editableData!.totalAmount = confirmedTotalAmount;
    _recalculateJournal();
    notifyListeners();
  }

  /// Explicitly applies confirmed Subtotal Sync
  void applyConfirmedSubtotalSync(double confirmedSubtotal) {
    if (_editableData == null) return;
    _editableData!.taxableAmount = confirmedSubtotal;
    _editableData!.subtotal = confirmedSubtotal;
    _recalculateJournal();
    notifyListeners();
  }

  /// Explicitly applies confirmed full mathematical recalculation
  void applyConfirmedFullRecalculation() {
    _recalculateTotals(recomputeLineTaxes: true, updateSummaryTotals: true);
    notifyListeners();
  }

  /// Explicitly applies confirmed tax supply switch
  void applyConfirmedTaxSupplySwitch({required bool targetInterState}) {
    _isInterStateOverride = targetInterState;
    if (_editableData != null) {
      for (var item in _editableData!.lineItems) {
        final rate = (item.gstRate != null && item.gstRate! > 0)
            ? item.gstRate!
            : ((item.igstRate ?? 0) > 0
                ? item.igstRate!
                : ((item.cgstRate ?? 0) + (item.sgstRate ?? 0) > 0
                    ? (item.cgstRate ?? 0) + (item.sgstRate ?? 0)
                    : 18.0));
        item.gstRate = rate;
        final lineTaxable = item.taxableAmount ?? (((item.quantity ?? 1.0) * (item.unitPrice ?? item.rate ?? 0.0)) - (item.discount ?? 0.0));
        if (targetInterState) {
          item.igstRate = rate;
          item.igstAmount = lineTaxable * (rate / 100);
          item.cgstRate = 0.0;
          item.cgstAmount = 0.0;
          item.sgstRate = 0.0;
          item.sgstAmount = 0.0;
        } else {
          final half = rate / 2;
          item.cgstRate = half;
          item.sgstRate = half;
          item.cgstAmount = lineTaxable * (half / 100);
          item.sgstAmount = lineTaxable * (half / 100);
          item.igstRate = 0.0;
          item.igstAmount = 0.0;
        }
        item.total = lineTaxable + (item.cgstAmount ?? 0.0) + (item.sgstAmount ?? 0.0) + (item.igstAmount ?? 0.0) + (item.cessAmount ?? 0.0);
      }
    }
    _recalculateTotals(recomputeLineTaxes: false, updateSummaryTotals: true);
    notifyListeners();
  }

  void recalculateTotals() {
    _recalculateTotals(recomputeLineTaxes: false, updateSummaryTotals: true);
    notifyListeners();
  }

  void _recalculateJournal({bool force = false}) {
    if (_editableData == null) return;
    if (_isJournalCustomized && !force) {
      _recalculateJournalTotals();
      return;
    }
    final taxable = _editableData!.taxableAmount ?? 0.0;
    final cgst = _editableData!.cgstAmount ?? 0.0;
    final sgst = _editableData!.sgstAmount ?? 0.0;
    final igst = _editableData!.igstAmount ?? 0.0;
    double tds = 0.0;
    if (_editableTds != null && _editableTds!.applicable == true) {
      if (_editableTds!.tdsAmount != null && _editableTds!.tdsAmount! > 0 && _editableTds!.tdsAmount! <= taxable) {
        tds = _editableTds!.tdsAmount!;
      } else {
        final isForeign = _activeInvoice?.isForeignService == true || _activeInvoice?.invoiceOrigin == 'FOREIGN_SERVICE';
        final rate = _editableTds!.tdsRate ?? (isForeign ? 20.0 : 10.0);
        tds = double.parse((taxable * (rate / 100)).toStringAsFixed(2));
        _editableTds!.tdsRate = rate;
        _editableTds!.tdsAmount = tds;
        _editableTds!.tdsBaseAmount = taxable;
      }
    }
    final isRcm = _editableTds?.isRcm ?? (_activeInvoice?.gstResult?.isReverseCharge == true);
    final total = _editableData!.totalAmount ?? (taxable + cgst + sgst + igst);

    // RCM calculation: If RCM is active, GST is not payable to vendor
    final payable = isRcm ? (taxable - tds) : (total - tds);

    final expenseAccount = (_editableData!.lineItems.isNotEmpty &&
            _editableData!.lineItems.first.accountName != null &&
            _editableData!.lineItems.first.accountName!.trim().isNotEmpty)
        ? _editableData!.lineItems.first.accountName!
        : 'Operating Expense / Purchase';

    List<JournalLine> lines = [
      JournalLine(
        accountCode: 'EXP-100',
        accountName: expenseAccount,
        debit: taxable,
        credit: 0.0,
        lineType: 'EXPENSE',
        provenance: 'AI_PREDICTED',
      ),
    ];

    if (cgst > 0) {
      lines.add(
        JournalLine(
          accountCode: 'GST-CGST-IN',
          accountName: isRcm ? 'RCM Input CGST Receivable' : 'Input CGST Receivable',
          debit: cgst,
          credit: 0.0,
          lineType: 'INPUT_TAX',
          provenance: 'DETERMINISTIC',
        ),
      );
    }
    if (sgst > 0) {
      lines.add(
        JournalLine(
          accountCode: 'GST-SGST-IN',
          accountName: isRcm ? 'RCM Input SGST Receivable' : 'Input SGST Receivable',
          debit: sgst,
          credit: 0.0,
          lineType: 'INPUT_TAX',
          provenance: 'DETERMINISTIC',
        ),
      );
    }
    if (igst > 0) {
      lines.add(
        JournalLine(
          accountCode: 'GST-IGST-IN',
          accountName: isRcm ? 'RCM Input IGST Receivable' : 'Input IGST Receivable',
          debit: igst,
          credit: 0.0,
          lineType: 'INPUT_TAX',
          provenance: 'DETERMINISTIC',
        ),
      );
    }

    if (isRcm && (cgst + sgst + igst) > 0) {
      lines.add(
        JournalLine(
          accountCode: 'GST-RCM-PAY',
          accountName: 'RCM Output GST Liability (To Govt)',
          debit: 0.0,
          credit: cgst + sgst + igst,
          lineType: 'RCM_LIABILITY',
          provenance: 'DETERMINISTIC',
        ),
      );
    }

    if (tds > 0) {
      lines.add(
        JournalLine(
          accountCode: 'TDS-PAY-200',
          accountName: 'TDS Payable (Section ${_editableTds?.tdsSection ?? "194C"})',
          debit: 0.0,
          credit: tds,
          lineType: 'TDS_PAYABLE',
          provenance: 'DETERMINISTIC',
        ),
      );
    }

    lines.add(
      JournalLine(
        accountCode: 'AP-VEND-001',
        accountName: 'Accounts Payable - ${_editableData?.vendorName ?? "Vendor"}',
        debit: 0.0,
        credit: payable > 0 ? payable : 0.0,
        lineType: 'ACCOUNTS_PAYABLE',
        provenance: 'DETERMINISTIC',
      ),
    );

    double d = 0;
    double c = 0;
    for (var l in lines) {
      d += l.debit;
      c += l.credit;
    }

    _editableJournal = JournalEntry(
      journalNumber: 'JRN-${_activeInvoice?.id ?? 0}',
      date: _editableData?.invoiceDate ?? DateTime.now().toIso8601String().split('T').first,
      referenceNumber: _editableData?.invoiceNumber,
      lines: lines,
      totalDebit: d,
      totalCredit: c,
      difference: (d - c).abs(),
      isBalanced: (d - c).abs() < 0.05,
    );
  }

  Future<bool> saveDraft() async {
    if (_activeInvoice == null) return false;
    _isSaving = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final updated = await _service.updateInvoice(
        _activeInvoice!.id,
        currentVlmOutput: {'data': _editableData?.toJson()},
        currentAccountingOutput: {
          'tds_assessment': _editableTds?.toJson(),
          if (_editableItc != null) 'itc_assessment': _editableItc?.toJson(),
        },
        journalEntry: _editableJournal?.toJson(),
      );
      _activeInvoice = updated;
      _isSaving = false;
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
      _isSaving = false;
      notifyListeners();
      return false;
    }
  }

  Future<bool> approveInvoice() async {
    if (_activeInvoice == null) return false;
    _isApproving = true;
    _errorMessage = null;
    notifyListeners();

    try {
      await saveDraft();
      final updated = await _service.approveInvoice(_activeInvoice!.id);
      _activeInvoice = updated;
      _isApproving = false;
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
      _isApproving = false;
      notifyListeners();
      return false;
    }
  }

  Future<bool> rejectInvoice(String reason) async {
    if (_activeInvoice == null) return false;
    _isRejecting = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final updated = await _service.rejectInvoice(_activeInvoice!.id, reason);
      _activeInvoice = updated;
      _isRejecting = false;
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
      _isRejecting = false;
      notifyListeners();
      return false;
    }
  }

  Future<bool> approveTds() async {
    if (_activeInvoice == null) return false;
    _errorMessage = null;
    notifyListeners();
    try {
      await _service.approveTds(_activeInvoice!.id);
      await loadInvoiceDetail(_activeInvoice!.id, silent: true);
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
      notifyListeners();
      return false;
    }
  }

  Future<bool> approveJournal() async {
    if (_activeInvoice == null) return false;
    _errorMessage = null;
    notifyListeners();
    try {
      await _service.approveJournal(_activeInvoice!.id);
      await loadInvoiceDetail(_activeInvoice!.id, silent: true);
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
      notifyListeners();
      return false;
    }
  }

  Future<bool> exportToZoho([dynamic targetId]) async {
    final invoiceId = targetId ?? _activeInvoice?.id;
    if (invoiceId == null || invoiceId.toString().isEmpty) {
      _errorMessage = 'No invoice selected for export.';
      return false;
    }
    _isExporting = true;
    _errorMessage = null;
    notifyListeners();

    try {
      // Save any pending user modifications first so latest COA/lines reach backend
      if (_activeInvoice != null && _editableData != null) {
        await saveDraft();
      }

      if (_activeInvoice != null && _activeInvoice!.displayStatus != 'approved' && _activeInvoice!.displayStatus != 'exported') {
        final approved = await approveInvoice();
        if (!approved) {
          _isExporting = false;
          notifyListeners();
          return false;
        }
      }

      await _service.exportToZoho(invoiceId);
      await loadInvoiceDetail(invoiceId);
      _isExporting = false;
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
      _isExporting = false;
      notifyListeners();
      return false;
    }
  }

  List<AuditLogEntry> _auditTrail = [];
  bool _isLoadingAudit = false;

  List<AuditLogEntry> get auditTrail => _auditTrail;
  bool get isLoadingAudit => _isLoadingAudit;

  Future<void> fetchAuditTrail(dynamic id) async {
    _isLoadingAudit = true;
    notifyListeners();
    try {
      _auditTrail = await _service.getAuditTrail(id);
    } catch (_) {
      _auditTrail = [];
    } finally {
      _isLoadingAudit = false;
      notifyListeners();
    }
  }

  Future<bool> submitPeriodDecision(dynamic id, String decision) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();
    try {
      await _service.submitPeriodDecision(id, decision);
      await loadInvoiceDetail(id);
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<Invoice> uploadInvoice({
    required List<int> bytes,
    required String filename,
  }) async {
    final inv = await _service.uploadInvoice(
      fileBytes: bytes,
      filename: filename,
    );
    _invoices.insert(0, inv);
    notifyListeners();
    return inv;
  }

  Future<bool> overrideClassification(dynamic id, String classification, String reason) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();
    try {
      await _service.overrideClassification(id, classification: classification, reason: reason);
      await loadInvoiceDetail(id);
      await fetchAuditTrail(id);
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> overrideExchangeRate(dynamic id, double rate, String reason) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();
    try {
      await _service.updateInvoice(
        id,
        exchangeRate: rate,
        fxOverrideReason: reason,
      );
      await loadInvoiceDetail(id);
      await fetchAuditTrail(id);
      return true;
    } catch (e) {
      _errorMessage = e.toString().replaceAll('Exception: ', '');
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
}
