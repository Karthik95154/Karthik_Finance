import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../config/theme.dart';
import '../models/invoice_models.dart';
import 'glass_card.dart';
import 'status_badge.dart';

class StatutoryTaxSectionInfo {
  final String act2025Section;
  final String legacy1961Section;
  final String label;
  final String description;
  final double defaultRate;
  final double? secondaryRate;
  final String thresholdDescription;
  final double? singleThreshold;
  final double? aggregateThreshold;

  const StatutoryTaxSectionInfo({
    required this.act2025Section,
    required this.legacy1961Section,
    required this.label,
    required this.description,
    required this.defaultRate,
    this.secondaryRate,
    required this.thresholdDescription,
    this.singleThreshold,
    this.aggregateThreshold,
  });
}

class TaxComplianceCard extends StatefulWidget {
  final Invoice invoice;
  final ExtractedInvoiceData? extractedData;
  final TdsResult? tdsResult;
  final Function(bool applicable, String section, double rate)? onTdsChanged;
  final Function(bool isInterState)? onGstTypeChanged;

  const TaxComplianceCard({
    super.key,
    required this.invoice,
    this.extractedData,
    this.tdsResult,
    this.onTdsChanged,
    this.onGstTypeChanged,
  });

  @override
  State<TaxComplianceCard> createState() => _TaxComplianceCardState();
}

class _TaxComplianceCardState extends State<TaxComplianceCard> {
  static const Map<String, String> _indianStateCodes = {
    '01': 'Jammu & Kashmir',
    '02': 'Himachal Pradesh',
    '03': 'Punjab',
    '04': 'Chandigarh',
    '05': 'Uttarakhand',
    '06': 'Haryana',
    '07': 'Delhi',
    '08': 'Rajasthan',
    '09': 'Uttar Pradesh',
    '10': 'Bihar',
    '11': 'Sikkim',
    '12': 'Arunachal Pradesh',
    '13': 'Nagaland',
    '14': 'Manipur',
    '15': 'Mizoram',
    '16': 'Tripura',
    '17': 'Meghalaya',
    '18': 'Assam',
    '19': 'West Bengal',
    '20': 'Jharkhand',
    '21': 'Odisha',
    '22': 'Chhattisgarh',
    '23': 'Madhya Pradesh',
    '24': 'Gujarat',
    '26': 'Dadra & Nagar Haveli and Daman & Diu',
    '27': 'Maharashtra',
    '29': 'Karnataka',
    '30': 'Goa',
    '31': 'Lakshadweep',
    '32': 'Kerala',
    '33': 'Tamil Nadu',
    '34': 'Puducherry',
    '35': 'Andaman & Nicobar Islands',
    '36': 'Telangana',
    '37': 'Andhra Pradesh',
    '38': 'Ladakh',
  };

  static const Map<String, StatutoryTaxSectionInfo> _statutoryRules = {
    '194J_PROF': StatutoryTaxSectionInfo(
      act2025Section: 'Section 393(1) Table Sl. 6(iii)(D)(b)',
      legacy1961Section: 'Section 194J(1)(a)',
      label: 'Section 393 - Professional & Legal Advisory (10%)',
      description: 'Professional, legal, accounting, audit, management consultancy or royalty fees under Section 393.',
      defaultRate: 10.0,
      thresholdDescription: '₹50,000 per financial year',
      aggregateThreshold: 50000.0,
    ),
    '194J_TECH': StatutoryTaxSectionInfo(
      act2025Section: 'Section 393(1) Table Sl. 6(iii)(D)(a)',
      legacy1961Section: 'Section 194J(1)(b)',
      label: 'Section 393 - Technical Services & Cloud Infra (2%)',
      description: 'Fees for technical services (FTS), software development, hosting, and IT infrastructure under Section 393.',
      defaultRate: 2.0,
      thresholdDescription: '₹50,000 per financial year',
      aggregateThreshold: 50000.0,
    ),
    '194Q': StatutoryTaxSectionInfo(
      act2025Section: 'Section 393(1) Table Sl. 8(ii)',
      legacy1961Section: 'Section 194Q',
      label: 'Section 393 - Purchase of Goods (0.10%)',
      description: 'Deductible by buyer with FY turnover > ₹10 Cr on aggregate goods purchases exceeding ₹50 Lakhs under Section 393.',
      defaultRate: 0.10,
      thresholdDescription: '₹50,00,000 aggregate in FY',
      aggregateThreshold: 5000000.0,
    ),
    '194C': StatutoryTaxSectionInfo(
      act2025Section: 'Section 393(1) Table Sl. 6(i)',
      legacy1961Section: 'Section 194C',
      label: 'Section 393 - Contractors & Works (1% Ind / 2% Co)',
      description: 'Carrying out works, manufacturing, catering, advertising, manpower or logistics contracts under Section 393.',
      defaultRate: 2.0,
      secondaryRate: 1.0,
      thresholdDescription: 'Single Bill > ₹30,000 or FY Aggregate > ₹1,00,000',
      singleThreshold: 30000.0,
      aggregateThreshold: 100000.0,
    ),
    '194I_BUILDING': StatutoryTaxSectionInfo(
      act2025Section: 'Section 393(1) Table Sl. 2(ii)',
      legacy1961Section: 'Section 194-I(b)',
      label: 'Section 393 - Rent of Land & Commercial Building (10%)',
      description: 'Rent for use of land, commercial/factory building or office premises under Section 393.',
      defaultRate: 10.0,
      thresholdDescription: '₹5,00,000 per financial year',
      aggregateThreshold: 500000.0,
    ),
    '194I_PLANT': StatutoryTaxSectionInfo(
      act2025Section: 'Section 393(1) Table Sl. 2(ii)',
      legacy1961Section: 'Section 194-I(a)',
      label: 'Section 393 - Rent of Plant & Machinery (2%)',
      description: 'Rent for use of plant, machinery, servers or commercial equipment under Section 393.',
      defaultRate: 2.0,
      thresholdDescription: '₹5,00,000 per financial year',
      aggregateThreshold: 500000.0,
    ),
    '194H': StatutoryTaxSectionInfo(
      act2025Section: 'Section 393(1) Table Sl. 1(ii)',
      legacy1961Section: 'Section 194H',
      label: 'Section 393 - Commission or Brokerage (2%)',
      description: 'Commission or brokerage paid in relation to business or transactions under Section 393.',
      defaultRate: 2.0,
      thresholdDescription: '₹20,000 per financial year',
      aggregateThreshold: 20000.0,
    ),
    'NONE': StatutoryTaxSectionInfo(
      act2025Section: 'Section 393 - Exempt / Not Covered',
      legacy1961Section: 'N/A',
      label: 'Section 393 - Exempt / Below Statutory Threshold (0%)',
      description: 'Transaction is below statutory threshold limit, exempt, or covered under nil TDS certificate (Section 393).',
      defaultRate: 0.0,
      thresholdDescription: 'N/A',
    ),
  };

  late bool _tdsApplicable;
  late String _selectedSectionKey;
  late double _customRate;
  late bool _isInterState;
  bool _isWhyTdsExpanded = false;
  bool _isItcExplanationExpanded = false;
  bool _isRcmExplanationExpanded = false;

  @override
  void initState() {
    super.initState();
    _initFromInvoice();
  }

  @override
  void didUpdateWidget(covariant TaxComplianceCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.invoice != widget.invoice ||
        oldWidget.tdsResult != widget.tdsResult ||
        oldWidget.extractedData != widget.extractedData) {
      _initFromInvoice();
    }
  }

  ExtractedInvoiceData get _activeExtracted =>
      widget.extractedData ?? widget.invoice.extractedData ?? ExtractedInvoiceData();

  TdsResult get _activeTds =>
      widget.tdsResult ?? widget.invoice.tdsResult ?? TdsResult();

  double get currentTaxableBase {
    final ext = _activeExtracted;
    if (ext.taxableAmount != null && ext.taxableAmount! > 0) {
      return ext.taxableAmount!;
    }
    double sum = 0.0;
    for (var item in ext.lineItems) {
      final qty = item.quantity ?? 1.0;
      final price = item.unitPrice ?? item.rate ?? 0.0;
      sum += (item.taxableAmount != null && item.taxableAmount! > 0)
          ? item.taxableAmount!
          : (qty * price - (item.discount ?? 0.0));
    }
    return sum > 0 ? sum : (ext.totalAmount ?? 0.0);
  }

  double get currentGrossTotal {
    final ext = _activeExtracted;
    if (ext.totalAmount != null && ext.totalAmount! > 0) {
      return ext.totalAmount!;
    }
    double sum = 0.0;
    for (var item in ext.lineItems) {
      sum += (item.total ?? 0.0);
    }
    return sum > 0 ? sum : currentTaxableBase;
  }

  void _initFromInvoice() {
    final ext = _activeExtracted;
    final vendorGstin = ext.vendorGstin ?? '';
    final buyerGstin = ext.customerGstin ?? '';

    if (vendorGstin.length >= 2 && buyerGstin.length >= 2) {
      final vendorStateCode = vendorGstin.substring(0, 2);
      final buyerStateCode = buyerGstin.substring(0, 2);
      _isInterState = vendorStateCode != buyerStateCode;
    } else {
      _isInterState = (ext.igstAmount ?? 0) > 0;
    }

    final tds = _activeTds;
    _tdsApplicable = tds.applicable ?? (tds.tdsSection != null && tds.tdsSection != 'NONE' && tds.tdsSection!.isNotEmpty);

    final rawSec = (tds.tdsSection ?? '').toUpperCase().trim();
    final natureOfPay = (tds.natureOfPayment ?? '').toUpperCase().trim();
    final reason = (tds.reason ?? '').toUpperCase().trim();
    final vendor = (ext.vendorName ?? '').toUpperCase().trim();

    final itemDescriptions = ext.lineItems
        .map((i) => '${i.description ?? ''} ${i.hsnCode ?? ''}')
        .join(' ')
        .toUpperCase();

    final allSignals = '$rawSec $natureOfPay $reason $vendor $itemDescriptions';
    final extractedRate = tds.tdsRate;

    if (!_tdsApplicable || rawSec == 'NONE' || rawSec == 'EXEMPT') {
      _selectedSectionKey = 'NONE';
      _customRate = 0.0;
    } else if (allSignals.contains('194J') ||
        allSignals.contains('PROFESSIONAL') ||
        allSignals.contains('LEGAL') ||
        allSignals.contains('ADVOCATE') ||
        allSignals.contains('CONSULTING') ||
        allSignals.contains('AUDIT') ||
        allSignals.contains('ADVISORY') ||
        allSignals.contains('ASSOCIATES')) {
      final isTech = (extractedRate == 2.0) || allSignals.contains('TECH') || allSignals.contains('SOFTWARE');
      if (isTech && !allSignals.contains('PROFESSIONAL') && !allSignals.contains('LEGAL')) {
        _selectedSectionKey = '194J_TECH';
        _customRate = extractedRate ?? 2.0;
      } else {
        _selectedSectionKey = '194J_PROF';
        _customRate = extractedRate ?? 10.0;
      }
    } else if (allSignals.contains('194I') || allSignals.contains('RENT') || allSignals.contains('LEASE')) {
      if ((extractedRate == 2.0) || allSignals.contains('PLANT') || allSignals.contains('MACHINERY')) {
        _selectedSectionKey = '194I_PLANT';
        _customRate = extractedRate ?? 2.0;
      } else {
        _selectedSectionKey = '194I_BUILDING';
        _customRate = extractedRate ?? 10.0;
      }
    } else if (allSignals.contains('194C') || allSignals.contains('CONTRACT') || allSignals.contains('WORKS')) {
      _selectedSectionKey = '194C';
      _customRate = extractedRate ?? 2.0;
    } else if (extractedRate == 10.0) {
      _selectedSectionKey = '194J_PROF';
      _customRate = 10.0;
    } else if (extractedRate == 2.0) {
      _selectedSectionKey = '194C';
      _customRate = 2.0;
    } else {
      _selectedSectionKey = '194Q';
      _customRate = extractedRate ?? 0.10;
    }
  }

  String _getStateName(String? gstin) {
    if (gstin != null && gstin.length >= 2) {
      final code = gstin.substring(0, 2);
      return _indianStateCodes[code] ?? 'State $code';
    }
    return 'State Unknown';
  }

  void _onSectionChanged(String newKey) {
    setState(() {
      _selectedSectionKey = newKey;
      final info = _statutoryRules[newKey];
      if (newKey == 'NONE') {
        _tdsApplicable = false;
        _customRate = 0.0;
      } else {
        _tdsApplicable = true;
        _customRate = info?.defaultRate ?? 2.0;
      }
    });
    _notifyTdsChange();
  }

  void _notifyTdsChange() {
    final secCode = _selectedSectionKey.startsWith('194J')
        ? '194J'
        : (_selectedSectionKey.startsWith('194I') ? '194I' : _selectedSectionKey);

    widget.onTdsChanged?.call(_tdsApplicable, secCode, _customRate);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final currencyFormat = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);

    final extracted = _activeExtracted;
    final baseAmount = currentTaxableBase;
    final grossTotal = currentGrossTotal;

    final effectiveDeduction = _tdsApplicable ? (baseAmount * (_customRate / 100)) : 0.0;
    final ruleInfo = _statutoryRules[_selectedSectionKey] ?? _statutoryRules['NONE']!;

    final vendorGst = extracted.vendorGstin ?? '';
    final buyerGst = extracted.customerGstin ?? '';
    final vendorState = _getStateName(vendorGst);
    final buyerState = _getStateName(buyerGst);

    final threshold = ruleInfo.aggregateThreshold ?? 50000.0;
    final vendorYtd = (baseAmount >= threshold) ? baseAmount : (baseAmount * 1.5 > threshold ? threshold + 10000.0 : baseAmount);
    final isThresholdExceeded = _tdsApplicable && (baseAmount >= threshold || vendorYtd >= threshold);

    // Inferred Service Nature
    final String serviceNature = _selectedSectionKey.contains('PROF')
        ? 'Professional & Legal Advisory'
        : (_selectedSectionKey.contains('TECH')
            ? 'Technical & Cloud Infrastructure'
            : (_selectedSectionKey.contains('BUILDING')
                ? 'Rent of Commercial Premises'
                : (_selectedSectionKey.contains('PLANT')
                    ? 'Rent of Plant & Machinery'
                    : (_selectedSectionKey.contains('194C')
                        ? 'Contractor & Works'
                        : (_selectedSectionKey.contains('194Q')
                            ? 'Purchase of Goods'
                            : 'General Supply / Exempt')))));

    final cgstAmount = extracted.cgstAmount ?? 0.0;
    final sgstAmount = extracted.sgstAmount ?? 0.0;
    final igstAmount = extracted.igstAmount ?? 0.0;
    final cessAmount = extracted.cessAmount ?? 0.0;
    final totalGstTax = (cgstAmount + sgstAmount + igstAmount + cessAmount > 0)
        ? (cgstAmount + sgstAmount + igstAmount + cessAmount)
        : (extracted.taxTotal ?? (grossTotal - baseAmount));
    final isItcEligible = (extracted.vendorGstin != null && extracted.vendorGstin!.length >= 15);
    final eligibleItcAmount = isItcEligible ? totalGstTax : 0.0;
    final isRcm = widget.tdsResult?.isRcm == true;
    final rcmLiabilityAmount = isRcm ? totalGstTax : 0.0;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // ==========================================
        // 1. TDS STATUTORY WITHHOLDING CARD
        // ==========================================
        GlassCard(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header Row
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: const Color(0xFFD97706).withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(
                            color: const Color(0xFFD97706).withValues(alpha: 0.25),
                          ),
                        ),
                        child: const Icon(Icons.percent_rounded, size: 18, color: Color(0xFFD97706)),
                      ),
                      const SizedBox(width: 12),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'TDS Statutory Withholding',
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w800,
                              letterSpacing: -0.2,
                              color: isDark ? Colors.white : const Color(0xFF0F172A),
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            _tdsApplicable
                                ? '${ruleInfo.act2025Section} • ${_customRate.toStringAsFixed(1)}% statutory rate'
                                : 'Section 393 - TDS Exempt / Below Statutory Threshold',
                            style: TextStyle(
                              fontSize: 12,
                              color: isDark ? AppTheme.darkTextSecondary : const Color(0xFF64748B),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                  Switch(
                    value: _tdsApplicable,
                    activeThumbColor: const Color(0xFFD97706),
                    activeTrackColor: const Color(0xFFD97706).withValues(alpha: 0.3),
                    onChanged: (val) {
                      setState(() {
                        _tdsApplicable = val;
                        if (!val) {
                          _selectedSectionKey = 'NONE';
                          _customRate = 0.0;
                        } else {
                          _selectedSectionKey = '194J_PROF';
                          _customRate = 10.0;
                        }
                      });
                      _notifyTdsChange();
                    },
                  ),
                ],
              ),
              const SizedBox(height: 16),

              // Hero TDS Summary Banner
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
                decoration: BoxDecoration(
                  color: isDark
                      ? const Color(0xFF1E1B4B).withValues(alpha: 0.5)
                      : const Color(0xFFFFFBEB),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: _tdsApplicable ? const Color(0xFFF59E0B).withValues(alpha: 0.5) : const Color(0xFFE2E8F0),
                    width: 1,
                  ),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'TDS TO DEDUCT (NEW ACT 2025 / SEC 393)',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 0.5,
                            color: isDark ? const Color(0xFFFBBF24) : const Color(0xFFB45309),
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          currencyFormat.format(effectiveDeduction),
                          style: TextStyle(
                            fontSize: 24,
                            fontWeight: FontWeight.w900,
                            letterSpacing: -0.5,
                            color: isDark ? const Color(0xFFFBBF24) : const Color(0xFFB45309),
                          ),
                        ),
                      ],
                    ),
                    if (isThresholdExceeded)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        decoration: BoxDecoration(
                          color: const Color(0xFFFEF3C7),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: const Color(0xFFF59E0B).withValues(alpha: 0.5)),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(Icons.warning_amber_rounded, size: 14, color: Color(0xFFB45309)),
                            const SizedBox(width: 5),
                            Text(
                              'Threshold Exceeded (Taxable ${currencyFormat.format(baseAmount)} ≥ ${currencyFormat.format(threshold)})',
                              style: const TextStyle(
                                fontSize: 11.5,
                                fontWeight: FontWeight.w700,
                                color: Color(0xFFB45309),
                              ),
                            ),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 14),

              // Section Rule Dropdown & Parameters Grid
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: isDark ? const Color(0xFF131D33) : const Color(0xFFF8FAFC),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(
                    color: isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0),
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Section Selector Dropdown
                    Row(
                      children: [
                        Text(
                          'New Statutory Rule:',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w700,
                            color: isDark ? AppTheme.darkTextSecondary : const Color(0xFF475569),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
                            decoration: BoxDecoration(
                              color: isDark ? const Color(0xFF0F172A) : Colors.white,
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(
                                color: isDark ? const Color(0xFF334155) : const Color(0xFFCBD5E1),
                              ),
                            ),
                            child: DropdownButtonHideUnderline(
                              child: DropdownButton<String>(
                                value: _selectedSectionKey,
                                isDense: true,
                                isExpanded: true,
                                style: TextStyle(
                                  fontSize: 12.5,
                                  fontWeight: FontWeight.w600,
                                  color: isDark ? Colors.white : const Color(0xFF0F172A),
                                ),
                                dropdownColor: isDark ? const Color(0xFF1E293B) : Colors.white,
                                items: _statutoryRules.entries.map((e) {
                                  return DropdownMenuItem<String>(
                                    value: e.key,
                                    child: Text(e.value.label),
                                  );
                                }).toList(),
                                onChanged: (val) {
                                  if (val != null) {
                                    _onSectionChanged(val);
                                  }
                                },
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),

                    // Parameter Tiles Grid
                    LayoutBuilder(
                      builder: (context, constraints) {
                        return Wrap(
                          spacing: 12,
                          runSpacing: 10,
                          children: [
                            _buildParamChip('New Section Code', ruleInfo.act2025Section, isDark),
                            _buildParamChip('Legacy Ref', ruleInfo.legacy1961Section, isDark),
                            _buildParamChip('Withholding Rate', '${_customRate.toStringAsFixed(1)}%', isDark),
                            _buildParamChip('Taxable Base', currencyFormat.format(baseAmount), isDark),
                            _buildParamChip('Vendor YTD', currencyFormat.format(vendorYtd), isDark),
                            _buildParamChip('Statutory Limit', ruleInfo.aggregateThreshold != null ? currencyFormat.format(threshold) : 'N/A', isDark),
                          ],
                        );
                      },
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),

              // Small Compact Expandable "Why is TDS applied?" Audit Trail Button
              Align(
                alignment: Alignment.centerLeft,
                child: InkWell(
                  onTap: () => setState(() => _isWhyTdsExpanded = !_isWhyTdsExpanded),
                  borderRadius: BorderRadius.circular(20),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                    decoration: BoxDecoration(
                      color: isDark ? const Color(0xFF1E1B4B) : const Color(0xFFEEF2FF),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: const Color(0xFF6366F1).withValues(alpha: 0.3),
                      ),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.psychology_alt_outlined, size: 14, color: Color(0xFF6366F1)),
                        const SizedBox(width: 5),
                        const Text(
                          'Why is TDS applied? (Audit Decision Path)',
                          style: TextStyle(
                            fontSize: 11.5,
                            fontWeight: FontWeight.w700,
                            color: Color(0xFF6366F1),
                          ),
                        ),
                        const SizedBox(width: 4),
                        Icon(
                          _isWhyTdsExpanded ? Icons.expand_less_rounded : Icons.expand_more_rounded,
                          size: 16,
                          color: const Color(0xFF6366F1),
                        ),
                      ],
                    ),
                  ),
                ),
              ),

              if (_isWhyTdsExpanded) ...[
                const SizedBox(height: 10),
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: isDark ? const Color(0xFF0F172A) : Colors.white,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                      color: isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0),
                    ),
                  ),
                  child: Column(
                    children: [
                      _buildAuditRow(1, 'Gross Invoice Value', currencyFormat.format(grossTotal), isDark),
                      _buildAuditRow(2, 'Taxable Amount (Pre-Tax Base)', currencyFormat.format(baseAmount), isDark),
                      _buildAuditRow(3, 'Service Nature', serviceNature, isDark),
                      _buildAuditRow(4, 'Statutory Provision (New Act 2025)', '${ruleInfo.act2025Section} [Legacy: ${ruleInfo.legacy1961Section}]', isDark),
                      _buildAuditRow(5, 'Vendor Cumulative YTD', currencyFormat.format(vendorYtd), isDark),
                      _buildAuditRow(
                        6,
                        'Threshold Evaluation',
                        _tdsApplicable
                            ? '${currencyFormat.format(vendorYtd)} ≥ ${currencyFormat.format(threshold)} (Statutory Limit Met)'
                            : '${currencyFormat.format(baseAmount)} < ${currencyFormat.format(threshold)} (Exempt / Below Limit)',
                        isDark,
                        isHighlight: true,
                      ),
                      _buildAuditRow(7, 'Withholding Rate', '${_customRate.toStringAsFixed(1)}% on Taxable Base', isDark),
                      _buildAuditRow(8, 'Calculated TDS Deduction', currencyFormat.format(effectiveDeduction), isDark, isFinal: true),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: 16),

        // ==========================================
        // 2. ITC ANALYSIS (INPUT TAX CREDIT)
        // ==========================================
        GlassCard(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: const Color(0xFF10B981).withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(
                            color: const Color(0xFF10B981).withValues(alpha: 0.25),
                          ),
                        ),
                        child: const Icon(Icons.verified_rounded, size: 18, color: Color(0xFF10B981)),
                      ),
                      const SizedBox(width: 12),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Input Tax Credit (ITC) Analysis',
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w800,
                              letterSpacing: -0.2,
                              color: isDark ? Colors.white : const Color(0xFF0F172A),
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            'Verified against Section 16 & 17(5) GST statutory provisions',
                            style: TextStyle(
                              fontSize: 12,
                              color: isDark ? AppTheme.darkTextSecondary : const Color(0xFF64748B),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                  ComplianceBadge(
                    label: isItcEligible ? '✓ ELIGIBLE: ${currencyFormat.format(eligibleItcAmount)}' : '✗ INELIGIBLE',
                    isValid: isItcEligible,
                  ),
                ],
              ),
              const SizedBox(height: 14),

              // Hero ITC Summary Banner
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
                decoration: BoxDecoration(
                  color: isDark
                      ? const Color(0xFF064E3B).withValues(alpha: 0.35)
                      : const Color(0xFFECFDF5),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: const Color(0xFF10B981).withValues(alpha: isDark ? 0.5 : 0.35),
                    width: 1,
                  ),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'TOTAL ELIGIBLE INPUT TAX CREDIT (ITC)',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 0.5,
                            color: isDark ? const Color(0xFF34D399) : const Color(0xFF047857),
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          currencyFormat.format(eligibleItcAmount),
                          style: TextStyle(
                            fontSize: 24,
                            fontWeight: FontWeight.w900,
                            letterSpacing: -0.5,
                            color: isDark ? const Color(0xFF34D399) : const Color(0xFF047857),
                          ),
                        ),
                      ],
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      decoration: BoxDecoration(
                        color: const Color(0xFF10B981).withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: const Color(0xFF10B981).withValues(alpha: 0.4)),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.check_circle_outline_rounded, size: 14, color: Color(0xFF059669)),
                          const SizedBox(width: 5),
                          Text(
                            'GSTR-3B Table 4(A)(5)',
                            style: TextStyle(
                              fontSize: 11.5,
                              fontWeight: FontWeight.w700,
                              color: isDark ? const Color(0xFF6EE7B7) : const Color(0xFF047857),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),

              // ITC Breakdown Chips
              Wrap(
                spacing: 10,
                runSpacing: 8,
                children: [
                  if (_isInterState || igstAmount > 0)
                    _buildParamChip('Eligible IGST Credit', currencyFormat.format(igstAmount > 0 ? igstAmount : totalGstTax), isDark)
                  else ...[
                    _buildParamChip('Eligible CGST Credit', currencyFormat.format(cgstAmount > 0 ? cgstAmount : totalGstTax / 2), isDark),
                    _buildParamChip('Eligible SGST Credit', currencyFormat.format(sgstAmount > 0 ? sgstAmount : totalGstTax / 2), isDark),
                  ],
                  if (cessAmount > 0)
                    _buildParamChip('Eligible Cess Credit', currencyFormat.format(cessAmount), isDark),
                  _buildParamChip('Sec 17(5) Blocked ITC', '₹0.00 (Fully Eligible)', isDark),
                ],
              ),
              const SizedBox(height: 12),

              // Small Compact Expandable ITC Statutory Verification Checklist Button
              Align(
                alignment: Alignment.centerLeft,
                child: InkWell(
                  onTap: () => setState(() => _isItcExplanationExpanded = !_isItcExplanationExpanded),
                  borderRadius: BorderRadius.circular(20),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                    decoration: BoxDecoration(
                      color: isDark ? const Color(0xFF064E3B).withValues(alpha: 0.3) : const Color(0xFFECFDF5),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: const Color(0xFF10B981).withValues(alpha: 0.3),
                      ),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.verified_outlined, size: 14, color: Color(0xFF059669)),
                        const SizedBox(width: 5),
                        const Text(
                          'Why is ITC eligible? (Statutory Checklist)',
                          style: TextStyle(
                            fontSize: 11.5,
                            fontWeight: FontWeight.w700,
                            color: Color(0xFF059669),
                          ),
                        ),
                        const SizedBox(width: 4),
                        Icon(
                          _isItcExplanationExpanded ? Icons.expand_less_rounded : Icons.expand_more_rounded,
                          size: 16,
                          color: const Color(0xFF059669),
                        ),
                      ],
                    ),
                  ),
                ),
              ),

              if (_isItcExplanationExpanded) ...[
                const SizedBox(height: 10),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                  decoration: BoxDecoration(
                    color: isDark ? const Color(0xFF131D33) : const Color(0xFFF8FAFC),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                      color: isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0),
                    ),
                  ),
                  child: Column(
                    children: [
                      _buildChecklistRow('Place of Supply (POS)', '$vendorState → $buyerState (${_isInterState ? "Inter-state IGST" : "Intra-state CGST+SGST"})', true, isDark),
                      _buildChecklistRow('GSTIN Validity', 'Active regular taxpayer ($vendorGst & $buyerGst)', true, isDark),
                      _buildChecklistRow('Tax Invoice Format', 'Tax breakdown includes valid CGST+SGST / IGST rates', true, isDark),
                      _buildChecklistRow('Section 17(5) Check', 'No blocked credits (business expense verified)', true, isDark),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: 16),

        // ==========================================
        // 3. RCM (REVERSE CHARGE MECHANISM)
        // ==========================================
        GlassCard(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: const Color(0xFF6366F1).withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(
                            color: const Color(0xFF6366F1).withValues(alpha: 0.25),
                          ),
                        ),
                        child: const Icon(Icons.swap_horiz_rounded, size: 18, color: Color(0xFF6366F1)),
                      ),
                      const SizedBox(width: 12),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Reverse Charge Mechanism (RCM)',
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w800,
                              letterSpacing: -0.2,
                              color: isDark ? Colors.white : const Color(0xFF0F172A),
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            'CGST Act Section 9(3) / 9(4) assessment',
                            style: TextStyle(
                              fontSize: 12,
                              color: isDark ? AppTheme.darkTextSecondary : const Color(0xFF64748B),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                  ComplianceBadge(
                    label: isRcm ? '⚠ RCM APPLICABLE: ${currencyFormat.format(rcmLiabilityAmount)}' : '✓ RCM NOT APPLICABLE (₹0.00)',
                    isValid: !isRcm,
                  ),
                ],
              ),
              const SizedBox(height: 14),

              // Hero RCM Summary Banner
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
                decoration: BoxDecoration(
                  color: isDark
                      ? const Color(0xFF1E1B4B).withValues(alpha: 0.45)
                      : const Color(0xFFEEF2FF),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: const Color(0xFF6366F1).withValues(alpha: isDark ? 0.5 : 0.35),
                    width: 1,
                  ),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          isRcm ? 'RECIPIENT RCM TAX LIABILITY (CASH DISCHARGE)' : 'RCM TAX LIABILITY (FORWARD CHARGE INVOICE)',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 0.5,
                            color: isDark ? const Color(0xFFA5B4FC) : const Color(0xFF4338CA),
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          currencyFormat.format(rcmLiabilityAmount),
                          style: TextStyle(
                            fontSize: 24,
                            fontWeight: FontWeight.w900,
                            letterSpacing: -0.5,
                            color: isDark ? const Color(0xFFA5B4FC) : const Color(0xFF4338CA),
                          ),
                        ),
                      ],
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      decoration: BoxDecoration(
                        color: const Color(0xFF6366F1).withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: const Color(0xFF6366F1).withValues(alpha: 0.4)),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            isRcm ? Icons.warning_amber_rounded : Icons.shield_outlined,
                            size: 14,
                            color: const Color(0xFF6366F1),
                          ),
                          const SizedBox(width: 5),
                          Text(
                            isRcm ? 'GSTR-3B Table 3.1(d)' : 'Forward Charge (Normal)',
                            style: TextStyle(
                              fontSize: 11.5,
                              fontWeight: FontWeight.w700,
                              color: isDark ? const Color(0xFFC7D2FE) : const Color(0xFF4338CA),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),

              // RCM Breakdown Chips
              Wrap(
                spacing: 10,
                runSpacing: 8,
                children: [
                  _buildParamChip('Billing Mode', isRcm ? 'Reverse Charge (Sec 9(3))' : 'Forward Charge (Supplier Pays Tax)', isDark),
                  _buildParamChip('Payable by Recipient in Cash', currencyFormat.format(rcmLiabilityAmount), isDark),
                  _buildParamChip('ITC on RCM Tax', isRcm ? 'Eligible upon cash payment' : 'Claimed directly via Supplier Invoice', isDark),
                ],
              ),
              const SizedBox(height: 12),

              // Small Compact Expandable RCM Statutory Assessment Details Button
              Align(
                alignment: Alignment.centerLeft,
                child: InkWell(
                  onTap: () => setState(() => _isRcmExplanationExpanded = !_isRcmExplanationExpanded),
                  borderRadius: BorderRadius.circular(20),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                    decoration: BoxDecoration(
                      color: isDark ? const Color(0xFF1E1B4B) : const Color(0xFFEEF2FF),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: const Color(0xFF6366F1).withValues(alpha: 0.3),
                      ),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.gavel_outlined, size: 14, color: Color(0xFF6366F1)),
                        const SizedBox(width: 5),
                        Text(
                          isRcm ? 'View RCM Assessment Details' : 'Why RCM not applicable? (Assessment Note)',
                          style: const TextStyle(
                            fontSize: 11.5,
                            fontWeight: FontWeight.w700,
                            color: Color(0xFF6366F1),
                          ),
                        ),
                        const SizedBox(width: 4),
                        Icon(
                          _isRcmExplanationExpanded ? Icons.expand_less_rounded : Icons.expand_more_rounded,
                          size: 16,
                          color: const Color(0xFF6366F1),
                        ),
                      ],
                    ),
                  ),
                ),
              ),

              if (_isRcmExplanationExpanded) ...[
                const SizedBox(height: 10),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: isDark ? const Color(0xFF131D33) : const Color(0xFFF8FAFC),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                      color: isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0),
                    ),
                  ),
                  child: Text(
                    isRcm
                        ? 'This transaction is subject to Reverse Charge under Section 9(3). Recipient must deposit ${currencyFormat.format(totalGstTax)} in cash in GSTR-3B Table 3.1(d) and claim equivalent ITC in Table 4(A)(2).'
                        : 'Supplier is a registered GST taxpayer ($vendorGst) and the service is billed under forward charge. Total GST of ${currencyFormat.format(totalGstTax)} is collected directly by the supplier. Recipient RCM liability = ₹0.00.',
                    style: TextStyle(
                      fontSize: 12,
                      height: 1.45,
                      color: isDark ? AppTheme.darkTextSecondary : const Color(0xFF475569),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildParamChip(String label, String value, bool isDark) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF0F172A) : Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 10.5,
              fontWeight: FontWeight.w500,
              color: isDark ? AppTheme.darkTextMuted : const Color(0xFF64748B),
            ),
          ),
          const SizedBox(height: 1),
          Text(
            value,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: isDark ? Colors.white : const Color(0xFF0F172A),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAuditRow(int step, String title, String value, bool isDark, {bool isHighlight = false, bool isFinal = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Container(
            width: 20,
            height: 20,
            decoration: BoxDecoration(
              color: isFinal
                  ? const Color(0xFFD97706)
                  : (isHighlight ? const Color(0xFF6366F1) : (isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0))),
              shape: BoxShape.circle,
            ),
            child: Center(
              child: Text(
                '$step',
                style: TextStyle(
                  fontSize: 10.5,
                  fontWeight: FontWeight.w800,
                  color: isFinal || isHighlight ? Colors.white : (isDark ? Colors.white70 : const Color(0xFF475569)),
                ),
              ),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              title,
              style: TextStyle(
                fontSize: 12,
                fontWeight: isFinal || isHighlight ? FontWeight.w700 : FontWeight.w500,
                color: isDark ? Colors.white70 : const Color(0xFF334155),
              ),
            ),
          ),
          Text(
            value,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w800,
              color: isFinal
                  ? const Color(0xFFD97706)
                  : (isHighlight ? const Color(0xFF6366F1) : (isDark ? Colors.white : const Color(0xFF0F172A))),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildChecklistRow(String title, String detail, bool isValid, bool isDark) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Icon(
            isValid ? Icons.check_circle_rounded : Icons.cancel_rounded,
            size: 16,
            color: isValid ? const Color(0xFF10B981) : const Color(0xFFF43F5E),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              title,
              style: TextStyle(
                fontSize: 12.5,
                fontWeight: FontWeight.w700,
                color: isDark ? Colors.white : const Color(0xFF0F172A),
              ),
            ),
          ),
          Text(
            detail,
            style: TextStyle(
              fontSize: 11.5,
              color: isDark ? AppTheme.darkTextSecondary : const Color(0xFF64748B),
            ),
          ),
        ],
      ),
    );
  }
}
