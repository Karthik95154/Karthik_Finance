import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../models/invoice_models.dart';
import '../providers/invoice_provider.dart';
import 'glass_card.dart';

class TdsComplianceCard extends StatefulWidget {
  final TdsResult? tds;
  final double taxableAmount;
  final String? vendorPan;

  const TdsComplianceCard({
    super.key,
    this.tds,
    required this.taxableAmount,
    this.vendorPan,
  });

  @override
  State<TdsComplianceCard> createState() => _TdsComplianceCardState();
}

class TdsStatutorySection {
  final String key;
  final String act2025Code;
  final String legacyCode;
  final String label;
  final String shortName;
  final String description;
  final double defaultRate;
  final double? secondaryRate;
  final double singleThreshold;
  final double aggregateThreshold;

  const TdsStatutorySection({
    required this.key,
    required this.act2025Code,
    required this.legacyCode,
    required this.label,
    required this.shortName,
    required this.description,
    required this.defaultRate,
    this.secondaryRate,
    this.singleThreshold = 0.0,
    required this.aggregateThreshold,
  });
}

class _TdsComplianceCardState extends State<TdsComplianceCard> {
  final _currencyFormat = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);

  static const List<TdsStatutorySection> _statutorySections = [
    TdsStatutorySection(
      key: '393_CONTRACTOR',
      act2025Code: 'Section 393(1) Sl. 6(i)',
      legacyCode: 'Sec 194C',
      label: 'Sec 393(1) Sl. 6(i) - Contractors & Works Contracts (1% Ind / 2% Co) [194C]',
      shortName: 'Contractors & Works Contracts',
      description: 'Carrying out works, manufacturing, manpower, catering, logistics & labor contracts.',
      defaultRate: 2.0,
      secondaryRate: 1.0,
      singleThreshold: 30000.0,
      aggregateThreshold: 100000.0,
    ),
    TdsStatutorySection(
      key: '393_TECH_FTS',
      act2025Code: 'Section 393(1) Sl. 6(iii)(D)(a)',
      legacyCode: 'Sec 194J(1)(b)',
      label: 'Sec 393(1) Sl. 6(iii)(D)(a) - Technical Services / FTS / Cloud & IT (2%) [194J]',
      shortName: 'Fees for Technical Services (FTS)',
      description: 'Fees for technical services (FTS), cloud infrastructure, software dev & IT support.',
      defaultRate: 2.0,
      aggregateThreshold: 50000.0,
    ),
    TdsStatutorySection(
      key: '393_PROFESSIONAL',
      act2025Code: 'Section 393(1) Sl. 6(iii)(D)(b)',
      legacyCode: 'Sec 194J(1)(a)',
      label: 'Sec 393(1) Sl. 6(iii)(D)(b) - Professional & Legal Consultancy (10%) [194J]',
      shortName: 'Professional Services & Legal',
      description: 'Professional, legal, accounting, audit, management advisory or royalty services.',
      defaultRate: 10.0,
      aggregateThreshold: 50000.0,
    ),
    TdsStatutorySection(
      key: '393_RENT_LAND_BLDG',
      act2025Code: 'Section 393(1) Sl. 2(ii)',
      legacyCode: 'Sec 194-I(b)',
      label: 'Sec 393(1) Sl. 2(ii) - Rent on Land, Building or Office (10%) [194-I]',
      shortName: 'Rent: Land & Commercial Premises',
      description: 'Rent for use of commercial/factory building, land or office premises.',
      defaultRate: 10.0,
      aggregateThreshold: 500000.0,
    ),
    TdsStatutorySection(
      key: '393_RENT_PLANT_MACH',
      act2025Code: 'Section 393(1) Sl. 2(ii)',
      legacyCode: 'Sec 194-I(a)',
      label: 'Sec 393(1) Sl. 2(ii) - Rent on Plant, Machinery & Equipment (2%) [194-I]',
      shortName: 'Rent: Plant & Machinery',
      description: 'Rent for use of plant, machinery, hardware servers or industrial equipment.',
      defaultRate: 2.0,
      aggregateThreshold: 500000.0,
    ),
    TdsStatutorySection(
      key: '393_PURCHASE_GOODS',
      act2025Code: 'Section 393(1) Sl. 8(ii)',
      legacyCode: 'Sec 194Q',
      label: 'Sec 393(1) Sl. 8(ii) - Purchase of Goods > ₹50L (0.10%) [194Q]',
      shortName: 'Purchase of Goods (>₹50L)',
      description: 'Deductible by buyer with FY turnover > ₹10 Cr on aggregate goods purchases > ₹50 Lakhs.',
      defaultRate: 0.10,
      aggregateThreshold: 5000000.0,
    ),
    TdsStatutorySection(
      key: '393_COMMISSION',
      act2025Code: 'Section 393(1) Sl. 1(ii)',
      legacyCode: 'Sec 194H',
      label: 'Sec 393(1) Sl. 1(ii) - Commission or Brokerage (2%) [194H]',
      shortName: 'Commission & Brokerage',
      description: 'Commission or brokerage paid in relation to business or transactions.',
      defaultRate: 2.0,
      aggregateThreshold: 20000.0,
    ),
    TdsStatutorySection(
      key: '393_INTEREST_OTHER',
      act2025Code: 'Section 393(1) Sl. 5(ii)',
      legacyCode: 'Sec 194A',
      label: 'Sec 393(1) Sl. 5(ii) - Interest Other than Securities (10%) [194A]',
      shortName: 'Interest (Deposits / Loans)',
      description: 'Interest payments to resident entities other than banking securities.',
      defaultRate: 10.0,
      aggregateThreshold: 50000.0,
    ),
    TdsStatutorySection(
      key: '393_DIVIDENDS',
      act2025Code: 'Section 393(1) Sl. 7',
      legacyCode: 'Sec 194',
      label: 'Sec 393(1) Sl. 7 - Dividend Distribution (10%) [194]',
      shortName: 'Dividends',
      description: 'Dividend distributed to resident shareholders.',
      defaultRate: 10.0,
      aggregateThreshold: 5000.0,
    ),
    TdsStatutorySection(
      key: '393_BENEFIT_PERQUISITE',
      act2025Code: 'Section 393(1) Sl. 8(iv)',
      legacyCode: 'Sec 194R',
      label: 'Sec 393(1) Sl. 8(iv) - Benefit or Perquisite in Business (10%) [194R]',
      shortName: 'Business Benefits & Perks',
      description: 'Perquisites or benefits provided in the course of carrying on business.',
      defaultRate: 10.0,
      aggregateThreshold: 20000.0,
    ),
    TdsStatutorySection(
      key: '393_PARTNER_REMUNERATION',
      act2025Code: 'Section 393(3) Sl. 7',
      legacyCode: 'Sec 194T',
      label: 'Sec 393(3) Sl. 7 - Partner Remuneration / Interest (10%) [194T]',
      shortName: 'Partner Remuneration & Interest',
      description: 'Salary, bonus, commission, remuneration or interest paid to partners of a firm.',
      defaultRate: 10.0,
      aggregateThreshold: 20000.0,
    ),
    TdsStatutorySection(
      key: '392_SALARY',
      act2025Code: 'Section 392',
      legacyCode: 'Sec 192',
      label: 'Section 392 - Salary & Employee Remuneration [192]',
      shortName: 'Salary & Remuneration',
      description: 'Salary and remuneration to employees subject to individual tax slab rates.',
      defaultRate: 10.0,
      aggregateThreshold: 300000.0,
    ),
    TdsStatutorySection(
      key: '393_NON_RESIDENT',
      act2025Code: 'Section 393(2), Table Sl. No. 17',
      legacyCode: 'Sec 195',
      label: 'Section 393(2), Table Sl. No. 17 - Foreign Remittance / Non-Resident (20%) [195]',
      shortName: 'Non-Resident Foreign Payments',
      description: 'Payments or remittances to non-residents or foreign corporate entities under Section 393(2) Table Sl. No. 17.',
      defaultRate: 20.0,
      aggregateThreshold: 0.0,
    ),
  ];

  static TdsStatutorySection _resolveSection(String? secQuery, double? rate) {
    if (secQuery == null || secQuery.isEmpty) {
      if (rate != null && (rate - 20.0).abs() < 0.1) {
        return _statutorySections[12]; // 393_NON_RESIDENT (20%)
      }
      return _statutorySections[0]; // Default: 393_CONTRACTOR (194C)
    }
    final q = secQuery.toUpperCase();

    // Exact key match
    for (final s in _statutorySections) {
      if (s.key == q || s.act2025Code.toUpperCase().contains(q)) {
        return s;
      }
    }

    // 195 / Foreign / 393(2) / Sl. 17 / Non-Resident
    if (q.contains('195') || q.contains('FOREIGN') || q.contains('NON_RESIDENT') || q.contains('393(2)') || q.contains('393 2') || q.contains('SL. NO. 17') || q.contains('SL 17') || q.contains('SL. 17') || (rate != null && (rate - 20.0).abs() < 0.1)) {
      return _statutorySections[12];
    }

    // 194J / Technical vs Professional disambiguation
    if (q.contains('194J') || q.contains('FTS') || q.contains('TECHNICAL') || q.contains('PROFESSIONAL')) {
      if ((rate != null && rate <= 2.5) || q.contains('TECH') || q.contains('FTS')) {
        return _statutorySections[1]; // 393_TECH_FTS (2%)
      }
      return _statutorySections[2]; // 393_PROFESSIONAL (10%)
    }

    // 194C / Contractor
    if (q.contains('194C') || q.contains('CONTRACT') || q.contains('WORK') || q.contains('MANPOWER') || q.contains('SECURITY')) {
      return _statutorySections[0];
    }

    // 194-I / Rent
    if (q.contains('194I') || q.contains('194-I') || q.contains('RENT')) {
      if ((rate != null && rate <= 2.5) || q.contains('PLANT') || q.contains('MACHIN')) {
        return _statutorySections[4]; // 393_RENT_PLANT_MACH (2%)
      }
      return _statutorySections[3]; // 393_RENT_LAND_BLDG (10%)
    }

    // 194Q / Purchase of Goods
    if (q.contains('194Q') || q.contains('GOODS')) {
      return _statutorySections[5];
    }

    // 194H / Commission
    if (q.contains('194H') || q.contains('COMMISSION') || q.contains('BROKERAGE')) {
      return _statutorySections[6];
    }

    // 194A / Interest
    if (q.contains('194A') || q.contains('INTEREST')) {
      return _statutorySections[7];
    }

    // 194 / Dividend
    if (q.contains('194') && !q.contains('194C') && !q.contains('194J') && !q.contains('194I') && !q.contains('194Q') && !q.contains('194H') && !q.contains('194A')) {
      return _statutorySections[8];
    }

    // 194R
    if (q.contains('194R') || q.contains('PERQUISITE')) {
      return _statutorySections[9];
    }

    // 194T
    if (q.contains('194T') || q.contains('PARTNER')) {
      return _statutorySections[10];
    }

    // 192 / Salary
    if (q.contains('192') || q.contains('SALARY') || q.contains('392')) {
      return _statutorySections[11];
    }

    return _statutorySections[0];
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final provider = context.watch<InvoiceProvider>();
    final tds = widget.tds ?? TdsResult();

    final isApplicable = tds.applicable == true;
    final section = tds.tdsSection ?? '194C';
    final rate = tds.tdsRate ?? 2.0;
    final baseAmount = tds.tdsBaseAmount ?? widget.taxableAmount;
    final tdsAmount = tds.tdsAmount ?? (isApplicable ? baseAmount * (rate / 100) : 0.0);
    final isApproved = tds.isApproved == true || tds.approvalStatus == 'APPROVED';
    final ytd = tds.ytdAmount ?? 0.0;
    final threshold = tds.thresholdLimit ?? 100000.0;
    final isForeign = section.contains('195') || (tds.reason?.toLowerCase().contains('non-resident') ?? false) || (tds.reason?.toLowerCase().contains('foreign') ?? false);
    final isPanValid = isForeign || (tds.panValid ?? (widget.vendorPan != null && widget.vendorPan!.length == 10));

    final previousYtd = tds.previousYtd ?? 0.0;
    final currentInvoiceAmount = (widget.taxableAmount > 0) ? widget.taxableAmount : (tds.currentInvoiceAmount ?? 0.0);
    final projectedYtd = previousYtd + currentInvoiceAmount;
    final isZoho = tds.isZohoYtd == true || previousYtd > 0;
    final thresholdExceeded = tds.thresholdExceeded ?? (projectedYtd >= threshold);
    final selectedStatutory = _resolveSection(section, rate);

    return GlassCard(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header Row
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.amber.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(Icons.account_balance_outlined, color: Colors.amber, size: 20),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(
                            'Statutory TDS Assessment',
                            style: theme.textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w700,
                              letterSpacing: 0.2,
                            ),
                          ),
                          const SizedBox(width: 8),
                          if (isApproved)
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: const Color(0xFF10B981).withOpacity(0.15),
                                borderRadius: BorderRadius.circular(12),
                                border: Border.all(color: const Color(0xFF10B981).withOpacity(0.4)),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  const Icon(Icons.verified_outlined, size: 12, color: Color(0xFF10B981)),
                                  const SizedBox(width: 4),
                                  Text(
                                    'APPROVED',
                                    style: theme.textTheme.labelSmall?.copyWith(
                                      color: const Color(0xFF10B981),
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                        ],
                      ),
                      Text(
                        'Direct Tax Code & Income-tax Act, 2025 (FY 2026-27) — Sections 392 / 393',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.textTheme.bodySmall?.color?.withOpacity(0.7),
                        ),
                      ),
                    ],
                  ),
                ),
                // Toggle TDS Applicable Switch
                Row(
                  children: [
                    Text(
                      isApplicable ? 'Applicable' : 'Exempt',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: isApplicable ? Colors.amber : Colors.grey,
                      ),
                    ),
                    const SizedBox(width: 6),
                    Switch.adaptive(
                      value: isApplicable,
                      activeColor: Colors.amber,
                      onChanged: (val) {
                        provider.updateTds(applicable: val);
                      },
                    ),
                  ],
                ),
              ],
            ),

            const SizedBox(height: 16),
            const Divider(height: 1),
            const SizedBox(height: 16),

            // PAN Compliance Banner
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: isPanValid ? Colors.blue.withOpacity(0.08) : Colors.red.withOpacity(0.08),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: isPanValid ? Colors.blue.withOpacity(0.2) : Colors.red.withOpacity(0.3),
                ),
              ),
              child: Row(
                children: [
                  Icon(
                    isPanValid ? Icons.check_circle_outline : Icons.warning_amber_rounded,
                    size: 18,
                    color: isPanValid ? Colors.blue : Colors.redAccent,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      isForeign
                          ? 'Foreign Service Provider (Non-Resident). Section 195 / Section 393(2) foreign remittance assessment applies.'
                          : (isPanValid
                              ? 'Vendor PAN is valid (${widget.vendorPan ?? "On File"}). Standard statutory rates apply.'
                              : 'Vendor PAN missing or invalid. Section 206AA mandates 20% higher withholding tax rate.'),
                      style: TextStyle(
                        fontSize: 12,
                        color: (isForeign || isPanValid) ? Colors.blue.shade300 : Colors.redAccent.shade100,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 16),

            // Zoho Books YTD Threshold Tracking Card
            Container(
              padding: const EdgeInsets.all(14),
              margin: const EdgeInsets.only(bottom: 16),
              decoration: BoxDecoration(
                color: theme.colorScheme.surfaceContainerHighest.withOpacity(0.3),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                  color: thresholdExceeded
                      ? Colors.amber.withOpacity(0.4)
                      : theme.dividerColor.withOpacity(0.5),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Row(
                        children: [
                          Icon(
                            isZoho ? Icons.cloud_done_rounded : Icons.history_rounded,
                            size: 16,
                            color: isZoho ? const Color(0xFF10B981) : Colors.blueGrey,
                          ),
                          const SizedBox(width: 6),
                          Text(
                            'Year-To-Date (YTD) Turnover Assessment',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                              color: theme.textTheme.bodyMedium?.color,
                            ),
                          ),
                        ],
                      ),
                      if (isZoho)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: const Color(0xFF10B981).withOpacity(0.15),
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: const Color(0xFF10B981).withOpacity(0.4)),
                          ),
                          child: const Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(Icons.bolt, size: 12, color: Color(0xFF10B981)),
                              SizedBox(width: 3),
                              Text(
                                'Zoho Books Synced',
                                style: TextStyle(
                                  fontSize: 10,
                                  fontWeight: FontWeight.bold,
                                  color: Color(0xFF10B981),
                                ),
                              ),
                            ],
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  // Breakdown Grid
                  LayoutBuilder(
                    builder: (context, constraints) {
                      final isNarrow = constraints.maxWidth < 600;
                      if (isNarrow) {
                        return Column(
                          children: [
                            Row(
                              children: [
                                Expanded(
                                  child: _buildYtdMetric(
                                    context,
                                    label: 'Zoho Previous YTD',
                                    value: _currencyFormat.format(previousYtd),
                                    subtitle: 'Prior bills this FY',
                                    icon: Icons.receipt_long_outlined,
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: _buildYtdMetric(
                                    context,
                                    label: 'Current Bill Pre-Tax',
                                    value: _currencyFormat.format(currentInvoiceAmount),
                                    subtitle: 'This invoice',
                                    icon: Icons.add_circle_outline,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            Row(
                              children: [
                                Expanded(
                                  child: _buildYtdMetric(
                                    context,
                                    label: 'Projected Total YTD',
                                    value: _currencyFormat.format(projectedYtd),
                                    subtitle: 'Cumulative total',
                                    icon: Icons.pie_chart_outline,
                                    isHighlight: true,
                                    isExceeded: thresholdExceeded,
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: _buildYtdMetric(
                                    context,
                                    label: 'Sec $section Threshold',
                                    value: _currencyFormat.format(threshold),
                                    subtitle: thresholdExceeded ? 'Exceeded' : 'Limit',
                                    icon: Icons.verified_user_outlined,
                                  ),
                                ),
                              ],
                            ),
                          ],
                        );
                      }
                      return Row(
                        children: [
                          Expanded(
                            child: _buildYtdMetric(
                              context,
                              label: 'Zoho Previous YTD',
                              value: _currencyFormat.format(previousYtd),
                              subtitle: 'Prior bills this FY',
                              icon: Icons.receipt_long_outlined,
                            ),
                          ),
                          const SizedBox(width: 8),
                          const Text('+', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: Colors.grey)),
                          const SizedBox(width: 8),
                          Expanded(
                            child: _buildYtdMetric(
                              context,
                              label: 'Current Bill Pre-Tax',
                              value: _currencyFormat.format(currentInvoiceAmount),
                              subtitle: 'This invoice',
                              icon: Icons.add_circle_outline,
                            ),
                          ),
                          const SizedBox(width: 8),
                          const Text('=', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: Colors.grey)),
                          const SizedBox(width: 8),
                          Expanded(
                            child: _buildYtdMetric(
                              context,
                              label: 'Projected Total YTD',
                              value: _currencyFormat.format(projectedYtd),
                              subtitle: 'Cumulative total',
                              icon: Icons.pie_chart_outline,
                              isHighlight: true,
                              isExceeded: thresholdExceeded,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: _buildYtdMetric(
                              context,
                              label: 'Sec $section Threshold',
                              value: _currencyFormat.format(threshold),
                              subtitle: thresholdExceeded ? 'Exceeded' : 'Limit',
                              icon: Icons.verified_user_outlined,
                            ),
                          ),
                        ],
                      );
                    },
                  ),
                  const SizedBox(height: 12),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(4),
                    child: LinearProgressIndicator(
                      value: threshold > 0 ? (projectedYtd / threshold).clamp(0.0, 1.0) : 1.0,
                      backgroundColor: theme.dividerColor.withOpacity(0.2),
                      valueColor: AlwaysStoppedAnimation<Color>(
                        thresholdExceeded ? Colors.amber.shade600 : const Color(0xFF10B981),
                      ),
                      minHeight: 6,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(
                        child: Text(
                          thresholdExceeded
                              ? '⚠️ Projected turnover exceeds ${_currencyFormat.format(threshold)} threshold. Statutory TDS mandatory under ${selectedStatutory.act2025Code} (${selectedStatutory.legacyCode}).'
                              : '✅ Within threshold limit (${_currencyFormat.format((threshold - projectedYtd).clamp(0.0, double.infinity))} remaining before TDS applies).',
                          style: TextStyle(
                            fontSize: 11,
                            color: thresholdExceeded ? Colors.amber.shade300 : const Color(0xFF10B981),
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                      Text(
                        '${((projectedYtd / (threshold > 0 ? threshold : 1.0)) * 100).toStringAsFixed(1)}%',
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          color: thresholdExceeded ? Colors.amber.shade300 : const Color(0xFF10B981),
                        ),
                      ),
                    ],
                  ),
                  if (thresholdExceeded && !isApplicable) ...[
                    const SizedBox(height: 8),
                    InkWell(
                      onTap: () {
                        provider.updateTds(applicable: true);
                      },
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        decoration: BoxDecoration(
                          color: Colors.amber.withOpacity(0.18),
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: Colors.amber),
                        ),
                        child: const Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.bolt, size: 14, color: Colors.amber),
                            SizedBox(width: 6),
                            Text(
                              'Click to Apply Statutory TDS',
                              style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.amber),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),

            // Section & Rates Configuration
            if (isApplicable) ...[
              Row(
                children: [
                  // TDS Section Selector (Income-tax Act 2025)
                  Expanded(
                    flex: 3,
                    child: DropdownButtonFormField<String>(
                      value: selectedStatutory.key,
                      isExpanded: true,
                      decoration: InputDecoration(
                        labelText: 'Statutory TDS Provision (Income-tax Act, 2025)',
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                      ),
                      items: _statutorySections.map((s) {
                        return DropdownMenuItem<String>(
                          value: s.key,
                          child: Text(
                            s.label,
                            style: const TextStyle(fontSize: 12),
                            overflow: TextOverflow.ellipsis,
                          ),
                        );
                      }).toList(),
                      onChanged: (newKey) {
                        if (newKey != null) {
                          final match = _statutorySections.firstWhere((s) => s.key == newKey);
                          provider.updateTds(
                            section: match.act2025Code,
                            rate: match.defaultRate,
                          );
                        }
                      },
                    ),
                  ),
                  const SizedBox(width: 14),
                  // Rate % Input
                  Expanded(
                    flex: 1,
                    child: TextFormField(
                      key: ValueKey('rate_$rate'),
                      initialValue: rate.toString(),
                      decoration: InputDecoration(
                        labelText: 'Rate %',
                        suffixText: '%',
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                      ),
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      onChanged: (val) {
                        final r = double.tryParse(val);
                        if (r != null) {
                          provider.updateTds(rate: r);
                        }
                      },
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),

              // Statutory Metadata Card for Selected Section
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                decoration: BoxDecoration(
                  color: Colors.indigo.withOpacity(0.06),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.indigo.withOpacity(0.25)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: Colors.indigo.withOpacity(0.18),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            selectedStatutory.act2025Code,
                            style: const TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.bold,
                              color: Colors.indigoAccent,
                            ),
                          ),
                        ),
                        const SizedBox(width: 6),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: Colors.amber.withOpacity(0.18),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            'Legacy: ${selectedStatutory.legacyCode}',
                            style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w600,
                              color: Colors.amber.shade300,
                            ),
                          ),
                        ),
                        const Spacer(),
                        Text(
                          selectedStatutory.singleThreshold > 0
                              ? 'Threshold: Single ${_currencyFormat.format(selectedStatutory.singleThreshold)} / FY ${_currencyFormat.format(selectedStatutory.aggregateThreshold)}'
                              : 'Threshold: FY ${_currencyFormat.format(selectedStatutory.aggregateThreshold)}',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w600,
                            color: theme.textTheme.bodySmall?.color,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      '${selectedStatutory.shortName}: ${selectedStatutory.description}',
                      style: TextStyle(
                        fontSize: 11,
                        color: theme.textTheme.bodySmall?.color?.withOpacity(0.9),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 14),
              // Base and Calculated TDS breakdown with editable inputs
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: TextFormField(
                      key: ValueKey('tds_base_$baseAmount'),
                      initialValue: baseAmount.toStringAsFixed(2),
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      decoration: const InputDecoration(
                        labelText: 'TDS Base Amount (Taxable ₹)',
                        border: OutlineInputBorder(),
                        isDense: true,
                        prefixIcon: Icon(Icons.account_balance_wallet_outlined, size: 15),
                      ),
                      onChanged: (val) {
                        final b = double.tryParse(val) ?? baseAmount;
                        provider.updateTds(tdsBaseAmount: b);
                      },
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextFormField(
                      key: ValueKey('tds_amt_$tdsAmount'),
                      initialValue: tdsAmount.toStringAsFixed(2),
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      decoration: const InputDecoration(
                        labelText: 'Withheld TDS (₹)',
                        border: OutlineInputBorder(),
                        isDense: true,
                        prefixIcon: Icon(Icons.percent, size: 15, color: Colors.amber),
                      ),
                      style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.amber),
                      onChanged: (val) {
                        final a = double.tryParse(val) ?? tdsAmount;
                        provider.updateTds(tdsAmount: a);
                      },
                    ),
                  ),
                ],
              ),
            ],

            const SizedBox(height: 12),
            TextFormField(
              key: ValueKey('tds_reason_${tds.reason}'),
              initialValue: tds.reason ?? '',
              maxLines: 2,
              decoration: const InputDecoration(
                labelText: 'TDS Assessment Rationale & Statutory Notes',
                border: OutlineInputBorder(),
                isDense: true,
                hintText: 'e.g. Applicable under Section 393(1) Sl. 6 for IT cloud services...',
              ),
              onChanged: (val) {
                provider.updateTds(reason: val);
              },
            ),

            const SizedBox(height: 16),

            // Approve TDS Button
            if (!isApproved && isApplicable)
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: () async {
                    final ok = await provider.approveTds();
                    if (context.mounted && ok) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('TDS Assessment approved successfully')),
                      );
                    }
                  },
                  icon: const Icon(Icons.check_circle_outline, size: 16, color: Colors.amber),
                  label: const Text('Approve Statutory TDS Assessment', style: TextStyle(color: Colors.amber)),
                  style: OutlinedButton.styleFrom(
                    side: const BorderSide(color: Colors.amber),
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildYtdMetric(
    BuildContext context, {
    required String label,
    required String value,
    required String subtitle,
    required IconData icon,
    bool isHighlight = false,
    bool isExceeded = false,
  }) {
    final theme = Theme.of(context);
    final borderColor = isHighlight
        ? (isExceeded ? Colors.amber.withOpacity(0.5) : const Color(0xFF10B981).withOpacity(0.5))
        : theme.dividerColor.withOpacity(0.3);
    final bgColor = isHighlight
        ? (isExceeded ? Colors.amber.withOpacity(0.08) : const Color(0xFF10B981).withOpacity(0.08))
        : theme.colorScheme.surfaceContainerHighest.withOpacity(0.2);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: borderColor),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                icon,
                size: 13,
                color: isHighlight
                    ? (isExceeded ? Colors.amber : const Color(0xFF10B981))
                    : theme.textTheme.bodySmall?.color,
              ),
              const SizedBox(width: 4),
              Expanded(
                child: Text(
                  label,
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                    color: theme.textTheme.bodySmall?.color,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.bold,
              color: isHighlight
                  ? (isExceeded ? Colors.amber.shade300 : const Color(0xFF10B981))
                  : theme.textTheme.bodyLarge?.color,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            subtitle,
            style: TextStyle(
              fontSize: 9,
              color: theme.textTheme.bodySmall?.color?.withOpacity(0.7),
            ),
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}

