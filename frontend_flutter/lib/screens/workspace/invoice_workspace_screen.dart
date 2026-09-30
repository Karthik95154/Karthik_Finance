import 'dart:async';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../../config/theme.dart';
import '../../models/invoice_models.dart';
import '../../providers/integration_provider.dart';
import '../../providers/invoice_provider.dart';
import '../../widgets/add_vendor_dialog.dart';
import '../../widgets/create_coa_dialog.dart';
import '../../widgets/document_preview_pane.dart';
import '../../widgets/financial_confirmation_dialog.dart';
import '../../widgets/financial_validation_card.dart';
import '../../widgets/foreign_service_fx_card.dart';
import '../../widgets/glass_card.dart';
import '../../widgets/gst_rcm_card.dart';
import '../../widgets/itc_compliance_card.dart';
import '../../widgets/journal_preview.dart';
import '../../widgets/line_item_table.dart';
import '../../widgets/reject_invoice_dialog.dart';
import '../../widgets/skeleton_loader.dart';
import '../../widgets/status_badge.dart';
import '../../widgets/tds_compliance_card.dart';

class InvoiceWorkspaceScreen extends StatefulWidget {
  final dynamic invoiceId;
  final bool isCustomerMode;
  final bool isReadOnly;

  const InvoiceWorkspaceScreen({
    super.key,
    required this.invoiceId,
    this.isCustomerMode = false,
    this.isReadOnly = false,
  });

  @override
  State<InvoiceWorkspaceScreen> createState() => _InvoiceWorkspaceScreenState();
}

class _InvoiceWorkspaceScreenState extends State<InvoiceWorkspaceScreen> {
  final ScrollController _workspaceScrollController = ScrollController();
  final GlobalKey _sec1Key = GlobalKey();
  final GlobalKey _sec2Key = GlobalKey();
  final GlobalKey _secFinKey = GlobalKey();
  final GlobalKey _secGstKey = GlobalKey();
  final GlobalKey _sec3Key = GlobalKey();
  final GlobalKey _sec4Key = GlobalKey();
  final GlobalKey _secBankKey = GlobalKey();
  final GlobalKey _sec5Key = GlobalKey();

  int _activeSectionIndex = 0;
  bool _isAutoScrolling = false;
  Timer? _pollingTimer;
  bool _showDocumentPreview = true;
  bool _isEditingFinancialSummary = false;

  @override
  void initState() {
    super.initState();
    _workspaceScrollController.addListener(_onScroll);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadAndCheckPolling();
    });
  }

  void _onScroll() {
    if (_isAutoScrolling) return;
    final keys = [_sec1Key, _sec2Key, _secFinKey, _secGstKey, _sec3Key, _sec4Key, _secBankKey, _sec5Key];
    for (int i = 0; i < keys.length; i++) {
      final ctx = keys[i].currentContext;
      if (ctx != null) {
        final box = ctx.findRenderObject() as RenderBox?;
        if (box != null && box.hasSize) {
          final pos = box.localToGlobal(Offset.zero);
          if (pos.dy >= 60 && pos.dy <= 320) {
            if (_activeSectionIndex != i && mounted) {
              setState(() => _activeSectionIndex = i);
            }
            break;
          }
        }
      }
    }
  }

  void _scrollToSection(int index) {
    setState(() => _activeSectionIndex = index);
    final key = switch (index) {
      0 => _sec1Key,
      1 => _sec2Key,
      2 => _secFinKey,
      3 => _secGstKey,
      4 => _sec3Key,
      5 => _sec4Key,
      6 => _secBankKey,
      7 => _sec5Key,
      _ => _sec1Key,
    };
    final ctx = key.currentContext;
    if (ctx != null) {
      _isAutoScrolling = true;
      Scrollable.ensureVisible(
        ctx,
        duration: const Duration(milliseconds: 350),
        curve: Curves.easeInOutCubic,
        alignment: 0.0,
      ).then((_) {
        Future.delayed(const Duration(milliseconds: 150), () {
          _isAutoScrolling = false;
        });
      });
    }
  }

  void _loadAndCheckPolling() async {
    final invProv = Provider.of<InvoiceProvider>(context, listen: false);
    await invProv.loadInvoiceDetail(widget.invoiceId);
    _startPollingIfProcessing();
  }

  void _startPollingIfProcessing() {
    _pollingTimer?.cancel();
    final invProv = Provider.of<InvoiceProvider>(context, listen: false);
    final status = invProv.activeInvoice?.status.toLowerCase() ?? '';
    if (status.contains('processing') || status.contains('pending')) {
      _pollingTimer = Timer.periodic(const Duration(seconds: 4), (timer) async {
        if (!mounted) {
          timer.cancel();
          return;
        }
        await invProv.loadInvoiceDetail(widget.invoiceId, silent: true);
        final currentStatus = invProv.activeInvoice?.status.toLowerCase() ?? '';
        if (!currentStatus.contains('processing') && !currentStatus.contains('pending')) {
          timer.cancel();
        }
      });
    }
  }

  @override
  void dispose() {
    _pollingTimer?.cancel();
    _workspaceScrollController.removeListener(_onScroll);
    _workspaceScrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final invProv = context.watch<InvoiceProvider>();
    final invoice = invProv.activeInvoice;
    final isMobile = MediaQuery.of(context).size.width < 1000;

    final isProcessing = invoice != null &&
        (invoice.status.toUpperCase() == 'PROCESSING' ||
            invoice.status.toUpperCase() == 'PROCESSING_VLM' ||
            invoice.status.toUpperCase() == 'PROCESSING_ACCOUNTING' ||
            invoice.status.toUpperCase() == 'EXTRACTING');

    if ((invProv.isLoading && invoice == null) || isProcessing) {
      final msg = isProcessing
          ? 'Vision AI is extracting invoice line items, statutory taxes & vendor details...'
          : 'Loading invoice workspace & compliance schedules...';
      return WorkspaceSkeletonView(statusMessage: msg);
    }

    if (invoice == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Invoice Workspace')),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.error_outline, size: 48, color: Colors.redAccent),
              const SizedBox(height: 12),
              Text(invProv.errorMessage ?? 'Invoice not found'),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () => invProv.loadInvoiceDetail(widget.invoiceId),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    final extData = invProv.editableData ?? invoice.extractedData ?? ExtractedInvoiceData();
    final tdsData = invProv.editableTds ?? invoice.tdsResult ?? TdsResult();
    final journalData = invProv.editableJournal ?? invoice.journalEntry ?? JournalEntry();
    final gstData = invProv.editableGst ?? invoice.gstResult;
    final itcData = invProv.editableItc ?? invoice.itcResult;
    final fvrData = invoice.financialValidationResult;
    final vendorStatus = invProv.vendorStatus;

    return Scaffold(
      appBar: _buildWorkspaceAppBar(context, invoice, invProv),
      body: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Left Pane: Document Viewer (Collapsible on wide screens)
          if (!isMobile && _showDocumentPreview)
            SizedBox(
              width: MediaQuery.of(context).size.width * 0.42,
              child: DocumentPreviewPane(
                invoice: invoice,
              ),
            ),

          // Divider between preview and form
          if (!isMobile && _showDocumentPreview)
            const VerticalDivider(width: 1, thickness: 1),

          // Right Pane: Full Interactive Workspace Form with Pinned Header
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Pinned Sticky Section Jump Bar (Always visible while scrolling)
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 10),
                  decoration: BoxDecoration(
                    color: isDark ? const Color(0xFF0B132B) : const Color(0xFFF8FAFC),
                    border: Border(
                      bottom: BorderSide(
                        color: isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0),
                        width: 1,
                      ),
                    ),
                  ),
                  child: _buildSectionJumpBar(context),
                ),

                // Scrollable Form Content
                Expanded(
                  child: SingleChildScrollView(
                    controller: _workspaceScrollController,
                    padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 18),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Zoho Vendor Verification & Onboarding Banner
                        AddVendorBanner(
                          vendorStatus: vendorStatus,
                          isAdding: invProv.isAddingVendor,
                          onAddVendor: () async {
                            final ok = await invProv.addVendorToZoho();
                            if (context.mounted && ok) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('Vendor added to Zoho Books successfully!')),
                              );
                            }
                          },
                        ),
                        const SizedBox(height: 12),

                        // Zoho Export Audit & Status Card
                        _buildZohoExportAuditCard(context, invoice, invProv),
                        const SizedBox(height: 16),

                        // Section 1: Header Information & Parties
                        Container(
                          key: _sec1Key,
                          child: _buildHeaderSection(context, extData, invProv),
                        ),
                        const SizedBox(height: 24),

                        // Foreign Service FX & Classification Boundary Card (Top of Line Items)
                        if (invoice.isForeign ||
                            invoice.isForeignService ||
                            invoice.invoiceOrigin == 'FOREIGN_SERVICE' ||
                            (invoice.originalCurrency != null && invoice.originalCurrency != 'INR') ||
                            (extData.currency != null && extData.currency != 'INR')) ...[
                          ForeignServiceFxCard(invoice: invoice),
                          const SizedBox(height: 24),
                        ],

                        // Section 2: Line Items Extraction & Tax Split
                        Container(
                          key: _sec2Key,
                          child: LineItemTableWidget(
                            lineItems: extData.lineItems,
                            onUpdate: (idx, updated) => invProv.updateLineItem(idx, updated),
                            onAdd: () => invProv.addLineItem(),
                            onDelete: (idx) => invProv.removeLineItem(idx),
                            isRcm: invProv.editableTds?.isRcm ??
                                (invoice.isForeignService ||
                                 invoice.invoiceOrigin == 'FOREIGN_SERVICE' ||
                                 gstData?.isReverseCharge == true),
                            invoiceOrigin: invoice.invoiceOrigin,
                            masterAccountNames: () {
                              try {
                                final integ = Provider.of<IntegrationProvider>(context, listen: false);
                                return integ.masterAccounts
                                    .map((a) => a.name)
                                    .where((n) => n.trim().isNotEmpty)
                                    .toList();
                              } catch (_) {
                                return <String>[];
                              }
                            }(),
                          ),
                        ),
                        const SizedBox(height: 24),

                        // Section 3: Financial Summary & Charges Reconciliation
                        Container(
                          key: _secFinKey,
                          child: _buildFinancialSummary(context, extData, tdsData, invoice, invProv),
                        ),
                        const SizedBox(height: 24),

                        // Section 4: GST & Supply Classification / RCM Engine
                        Container(
                          key: _secGstKey,
                          child: GstRcmCard(
                            gstResult: gstData,
                            extractedData: extData,
                            isRcmActive: tdsData.isRcm == true,
                          ),
                        ),
                        const SizedBox(height: 24),

                        // Section 5: Statutory TDS Assessment with YTD Thresholds
                        Container(
                          key: _sec3Key,
                          child: TdsComplianceCard(
                            tds: tdsData,
                            taxableAmount: extData.taxableAmount ?? 0.0,
                            vendorPan: extData.vendorPan,
                          ),
                        ),
                        const SizedBox(height: 24),

                        // Section 6: Input Tax Credit (ITC) Section 16/17(5) Breakdown
                        Container(
                          key: _sec4Key,
                          child: ItcComplianceCard(
                            itcResult: itcData,
                            totalGstTax: extData.taxTotal ?? 0.0,
                          ),
                        ),
                        const SizedBox(height: 24),

                        // Section 7: Vendor Bank Details & Payment Settlement
                        Container(
                          key: _secBankKey,
                          child: _buildBankDetailsSection(context, extData),
                        ),
                        const SizedBox(height: 24),

                        // Section 8: Double-Entry Balanced General Ledger Journal
                        Container(
                          key: _sec5Key,
                          child: JournalPreviewWidget(
                            journal: journalData,
                            isCustomized: invProv.isJournalCustomized,
                            onLineChanged: (idx, updated) => invProv.updateJournalLine(idx, updated),
                            onAddLine: () => invProv.addJournalLine(),
                            onDeleteLine: (idx) => invProv.removeJournalLine(idx),
                            onResetToAuto: () => invProv.resetJournalToAuto(),
                          ),
                        ),
                        const SizedBox(height: 40),
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

  Widget _buildFinancialSummary(BuildContext context, ExtractedInvoiceData extData, TdsResult tdsData, Invoice invoice, InvoiceProvider invProv) {
    final currencyFormat = NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2);
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    final subtotal = extData.taxableAmount ?? extData.subtotal ?? 0.0;
    final cgst = extData.cgstAmount ?? 0.0;
    final sgst = extData.sgstAmount ?? 0.0;
    final igst = extData.igstAmount ?? 0.0;
    final cess = extData.cessAmount ?? 0.0;
    final totalTax = (cgst + sgst + igst + cess > 0) ? (cgst + sgst + igst + cess) : (extData.taxTotal ?? 0.0);
    final discount = extData.discountTotal ?? 0.0;
    final shipping = extData.shippingCharges ?? 0.0;
    final otherCharges = extData.otherCharges ?? 0.0;
    final adjustment = extData.adjustment ?? 0.0;
    final roundOff = extData.roundOff ?? 0.0;

    final isRcm = invProv.editableTds?.isRcm ??
        (invoice.isForeignService ||
         invoice.invoiceOrigin == 'FOREIGN_SERVICE' ||
         invoice.gstResult?.isReverseCharge == true);

    // For Forward Charge invoices: vendor invoice total includes taxable + tax
    // For Reverse Charge (RCM / Foreign Services): vendor bills taxable subtotal, while 18% IGST is self-assessed and paid to Govt.
    // Full Statutory Invoice Grand Total is always Subtotal + Taxes.
    final calculatedGrandTotal = subtotal + totalTax - discount + shipping + otherCharges + adjustment + roundOff;
    final extractedGrandTotal = extData.totalAmount;
    final hasTotalMismatch = extractedGrandTotal != null &&
        extractedGrandTotal > 0 &&
        !((extractedGrandTotal - calculatedGrandTotal).abs() <= 1.0 || (isRcm && (extractedGrandTotal - subtotal).abs() <= 1.0));
    final totalDiff = hasTotalMismatch ? (extractedGrandTotal - calculatedGrandTotal).abs() : 0.0;

    final lineItemsSum = extData.lineItems.fold<double>(0.0, (acc, it) => acc + (it.taxableAmount ?? 0.0));
    final hasLineSumMismatch = extData.lineItems.isNotEmpty && (lineItemsSum - subtotal).abs() > 1.0;
    final lineSumDiff = hasLineSumMismatch ? (lineItemsSum - subtotal).abs() : 0.0;

    final grandTotal = calculatedGrandTotal;

    final tdsAmount = (tdsData.applicable == true) ? (tdsData.tdsAmount ?? tdsData.calculatedTdsAmount ?? 0.0) : 0.0;
    final netPayable = (isRcm ? subtotal : grandTotal) - tdsAmount;

    final hasAnyMismatch = hasTotalMismatch || hasLineSumMismatch;

    final isTdsApplicable = tdsData.applicable == true;
    final tdsSectionLabel = tdsData.tdsSection ?? '194C';
    final tdsRateVal = tdsData.tdsRate ?? 2.0;

    return GlassCard(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Section Top Bar with Statutory Compliance & Reconciliation Badges
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(7),
                    decoration: BoxDecoration(
                      color: hasAnyMismatch
                          ? const Color(0xFFF59E0B).withValues(alpha: 0.15)
                          : const Color(0xFF10B981).withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Icon(
                      hasAnyMismatch ? Icons.warning_amber_rounded : Icons.account_balance_outlined,
                      color: hasAnyMismatch ? const Color(0xFFF59E0B) : const Color(0xFF10B981),
                      size: 18,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Financial Settlement & Tax Engine',
                        style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold, letterSpacing: 0.2),
                      ),
                      Text(
                        'Double-entry statutory aggregation with live GST, TDS & RCM reconciliation',
                        style: TextStyle(fontSize: 11, color: theme.textTheme.bodySmall?.color?.withOpacity(0.75)),
                      ),
                    ],
                  ),
                ],
              ),
              Wrap(
                spacing: 8,
                runSpacing: 6,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  // Place of Supply Status Pill
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
                    decoration: BoxDecoration(
                      color: isDark ? const Color(0xFF0284C7).withValues(alpha: 0.18) : const Color(0xFFE0F2FE),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(
                        color: const Color(0xFF0284C7).withValues(alpha: 0.4),
                      ),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(
                          Icons.location_on_rounded,
                          size: 12,
                          color: Color(0xFF0284C7),
                        ),
                        const SizedBox(width: 4),
                        Text(
                          'POS: ${extData.placeOfSupply ?? (invProv.isInterState ? "Inter-State (IGST)" : "Intra-State (CGST+SGST)")}',
                          style: TextStyle(
                            fontSize: 10.5,
                            fontWeight: FontWeight.w600,
                            color: isDark ? const Color(0xFF38BDF8) : const Color(0xFF0369A1),
                          ),
                        ),
                      ],
                    ),
                  ),

                  // RCM Status Pill
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
                    decoration: BoxDecoration(
                      color: isRcm
                          ? (isDark ? const Color(0xFF6366F1).withValues(alpha: 0.2) : const Color(0xFFEEF2FF))
                          : (isDark ? Colors.white.withValues(alpha: 0.05) : const Color(0xFFF1F5F9)),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(
                        color: isRcm ? const Color(0xFF6366F1).withValues(alpha: 0.4) : theme.dividerColor.withOpacity(0.3),
                      ),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          isRcm ? Icons.swap_horiz_rounded : Icons.arrow_forward_rounded,
                          size: 12,
                          color: isRcm ? const Color(0xFF6366F1) : Colors.grey,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          isRcm ? 'RCM Active (Sec 9(3))' : 'Forward Charge',
                          style: TextStyle(
                            fontSize: 10.5,
                            fontWeight: FontWeight.w600,
                            color: isRcm ? (isDark ? const Color(0xFFA5B4FC) : const Color(0xFF4338CA)) : Colors.grey,
                          ),
                        ),
                      ],
                    ),
                  ),

                  // TDS Status Pill
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
                    decoration: BoxDecoration(
                      color: isTdsApplicable
                          ? (isDark ? const Color(0xFFF59E0B).withValues(alpha: 0.18) : const Color(0xFFFEF3C7))
                          : (isDark ? Colors.white.withValues(alpha: 0.05) : const Color(0xFFF1F5F9)),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(
                        color: isTdsApplicable ? const Color(0xFFF59E0B).withValues(alpha: 0.4) : theme.dividerColor.withOpacity(0.3),
                      ),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          Icons.security_outlined,
                          size: 12,
                          color: isTdsApplicable ? const Color(0xFFD97706) : Colors.grey,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          isTdsApplicable ? 'TDS u/s $tdsSectionLabel ($tdsRateVal%)' : 'TDS Non-Applicable',
                          style: TextStyle(
                            fontSize: 10.5,
                            fontWeight: FontWeight.w600,
                            color: isTdsApplicable ? (isDark ? const Color(0xFFFBBF24) : const Color(0xFFB45309)) : Colors.grey,
                          ),
                        ),
                      ],
                    ),
                  ),

                  // Auto-Reconciliation Badge
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
                    decoration: BoxDecoration(
                      color: hasAnyMismatch
                          ? (isDark ? const Color(0xFFEF4444).withValues(alpha: 0.18) : const Color(0xFFFEE2E2))
                          : (isDark ? const Color(0xFF10B981).withValues(alpha: 0.15) : const Color(0xFFECFDF5)),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(
                        color: hasAnyMismatch
                            ? const Color(0xFFEF4444).withValues(alpha: 0.4)
                            : const Color(0xFF10B981).withValues(alpha: 0.3),
                      ),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          hasAnyMismatch ? Icons.error_outline : Icons.check_circle_outline,
                          size: 12,
                          color: hasAnyMismatch ? const Color(0xFFDC2626) : const Color(0xFF059669),
                        ),
                        const SizedBox(width: 4),
                        Text(
                          hasAnyMismatch ? 'Math Mismatch' : '100% Reconciled',
                          style: TextStyle(
                            fontSize: 10.5,
                            fontWeight: FontWeight.bold,
                            color: hasAnyMismatch
                                ? (isDark ? const Color(0xFFFCA5A5) : const Color(0xFFB91C1C))
                                : (isDark ? const Color(0xFF34D399) : const Color(0xFF059669)),
                          ),
                        ),
                      ],
                    ),
                  ),

                  // Edit Figures Toggle Button
                  ElevatedButton.icon(
                    onPressed: () {
                      setState(() {
                        _isEditingFinancialSummary = !_isEditingFinancialSummary;
                      });
                    },
                    icon: Icon(
                      _isEditingFinancialSummary ? Icons.check_circle_rounded : Icons.tune_rounded,
                      size: 13,
                    ),
                    label: Text(_isEditingFinancialSummary ? 'Done Editing' : 'Edit Figures'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _isEditingFinancialSummary ? const Color(0xFF10B981) : const Color(0xFF0284C7),
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      textStyle: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                      visualDensity: VisualDensity.compact,
                    ),
                  ),
                ],
              ),
            ],
          ),

          // Inline Error Banners Directly on Discrepant Fields
          if (hasTotalMismatch) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: isDark ? const Color(0xFF78350F).withValues(alpha: 0.35) : const Color(0xFFFEF3C7),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: const Color(0xFFF59E0B)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.warning_amber_rounded, color: Color(0xFFD97706), size: 18),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Invoice Total Discrepancy: Extracted ${currencyFormat.format(extractedGrandTotal)} vs Calculated ${currencyFormat.format(calculatedGrandTotal)} (Diff: ${currencyFormat.format(totalDiff)})',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: isDark ? const Color(0xFFFDE68A) : const Color(0xFF92400E),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  ElevatedButton.icon(
                    onPressed: () async {
                      final confirmed = await showFinancialConfirmationDialog(
                        context: context,
                        actionTitle: 'Confirm Auto-Fix Invoice Grand Total',
                        reason: 'The physical invoice total (${currencyFormat.format(extractedGrandTotal)}) does not match the sum of Taxable Subtotal, Taxes, and Additional Charges (${currencyFormat.format(calculatedGrandTotal)}).',
                        formulaExplanation: 'Taxable Subtotal (${currencyFormat.format(subtotal)}) + Taxes (${currencyFormat.format(totalTax)}) - Discount (${currencyFormat.format(discount)}) + Freight (${currencyFormat.format(shipping)}) + Other (${currencyFormat.format(otherCharges)}) + RoundOff/Adj (${currencyFormat.format(adjustment + roundOff)}) = ${currencyFormat.format(calculatedGrandTotal)}',
                        comparisons: [
                          FinancialFieldComparison(
                            label: 'Invoice Grand Total',
                            currentValue: currencyFormat.format(extractedGrandTotal),
                            proposedValue: currencyFormat.format(calculatedGrandTotal),
                            difference: (calculatedGrandTotal >= (extractedGrandTotal ?? 0))
                                ? '+${currencyFormat.format(calculatedGrandTotal - (extractedGrandTotal ?? 0))}'
                                : '-${currencyFormat.format((extractedGrandTotal ?? 0) - calculatedGrandTotal)}',
                            isDifferent: true,
                            note: 'Will replace physical invoice extracted total in financial records',
                          ),
                          FinancialFieldComparison(
                            label: 'Taxable Subtotal',
                            currentValue: currencyFormat.format(subtotal),
                            proposedValue: currencyFormat.format(subtotal),
                            difference: '₹0.00 (Preserved)',
                            isDifferent: false,
                          ),
                          FinancialFieldComparison(
                            label: 'Total GST & Cess',
                            currentValue: currencyFormat.format(totalTax),
                            proposedValue: currencyFormat.format(totalTax),
                            difference: '₹0.00 (Preserved)',
                            isDifferent: false,
                          ),
                        ],
                      );

                      if (confirmed && context.mounted) {
                        invProv.applyConfirmedTotalFix(calculatedGrandTotal);
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text('Grand Total updated to ${currencyFormat.format(calculatedGrandTotal)} after user confirmation.'),
                            backgroundColor: const Color(0xFF059669),
                            behavior: SnackBarBehavior.floating,
                          ),
                        );
                      }
                    },
                    icon: const Icon(Icons.auto_fix_high, size: 13),
                    label: const Text('Auto-Fix Total'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFFD97706),
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      textStyle: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.bold),
                    ),
                  ),
                ],
              ),
            ),
          ],

          if (hasLineSumMismatch) ...[
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: isDark ? const Color(0xFF78350F).withValues(alpha: 0.35) : const Color(0xFFFEF3C7),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: const Color(0xFFF59E0B)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.warning_amber_rounded, color: Color(0xFFD97706), size: 18),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Subtotal Discrepancy: Line items sum to ${currencyFormat.format(lineItemsSum)} but Subtotal is ${currencyFormat.format(subtotal)} (Diff: ${currencyFormat.format(lineSumDiff)})',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: isDark ? const Color(0xFFFDE68A) : const Color(0xFF92400E),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  ElevatedButton.icon(
                    onPressed: () async {
                      final confirmed = await showFinancialConfirmationDialog(
                        context: context,
                        actionTitle: 'Confirm Sync Subtotal with Line Items',
                        reason: 'Line items sum to ${currencyFormat.format(lineItemsSum)}, but the extracted Taxable Subtotal is ${currencyFormat.format(subtotal)} (Variance: ${currencyFormat.format(lineSumDiff)}).',
                        formulaExplanation: 'Aggregated sum across ${extData.lineItems.length} line items = ${currencyFormat.format(lineItemsSum)}',
                        comparisons: [
                          FinancialFieldComparison(
                            label: 'Taxable Subtotal',
                            currentValue: currencyFormat.format(subtotal),
                            proposedValue: currencyFormat.format(lineItemsSum),
                            difference: (lineItemsSum >= subtotal)
                                ? '+${currencyFormat.format(lineItemsSum - subtotal)}'
                                : '-${currencyFormat.format(subtotal - lineItemsSum)}',
                            isDifferent: true,
                            note: 'Replaces subtotal with calculated sum of line items',
                          ),
                          FinancialFieldComparison(
                            label: 'Line Items Count',
                            currentValue: '${extData.lineItems.length} items',
                            proposedValue: '${extData.lineItems.length} items',
                            difference: 'Unchanged',
                            isDifferent: false,
                          ),
                        ],
                      );

                      if (confirmed && context.mounted) {
                        invProv.applyConfirmedSubtotalSync(lineItemsSum);
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text('Taxable Subtotal updated to ${currencyFormat.format(lineItemsSum)} after user confirmation.'),
                            backgroundColor: const Color(0xFF0284C7),
                            behavior: SnackBarBehavior.floating,
                          ),
                        );
                      }
                    },
                    icon: const Icon(Icons.sync, size: 13),
                    label: const Text('Sync Subtotal'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF0284C7),
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      textStyle: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.bold),
                    ),
                  ),
                ],
              ),
            ),
          ],

          const Divider(height: 24),

          // Primary Financial Metrics Row
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: theme.colorScheme.surfaceContainerHighest.withOpacity(0.25),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: theme.dividerColor.withOpacity(0.3)),
            ),
            child: Column(
              children: [
                // Top Row: Core Taxable Base, Total Taxes, Grand Total, Net Payable
                Row(
                  children: [
                    Expanded(
                      child: _buildSummaryCard(
                        context,
                        label: 'Taxable Subtotal',
                        value: currencyFormat.format(subtotal),
                        foreignValue: (invoice.isForeign || invoice.isForeignService || invoice.invoiceOrigin == 'FOREIGN_SERVICE' || (invoice.originalCurrency != null && invoice.originalCurrency != 'INR')) && (invoice.originalTaxableAmount != null || extData.originalTaxableAmount != null)
                            ? '${invoice.originalCurrency ?? extData.currency ?? 'USD'} ${NumberFormat('#,##0.00').format(invoice.originalTaxableAmount ?? extData.originalTaxableAmount ?? extData.taxableAmount ?? 0.0)}'
                            : null,
                        subtitle: 'Assessable Base Amount',
                        icon: Icons.account_balance_wallet_outlined,
                        isWarning: hasLineSumMismatch,
                        onTap: () => setState(() => _isEditingFinancialSummary = true),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _buildSummaryCard(
                        context,
                        label: 'Total GST & CESS',
                        value: currencyFormat.format(totalTax),
                        subtitle: 'Aggregated Tax Levy',
                        icon: Icons.receipt_long_outlined,
                        onTap: () => setState(() => _isEditingFinancialSummary = true),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _buildSummaryCard(
                        context,
                        label: 'Invoice Grand Total',
                        value: currencyFormat.format(grandTotal),
                        foreignValue: (invoice.isForeign || invoice.isForeignService || invoice.invoiceOrigin == 'FOREIGN_SERVICE' || (invoice.originalCurrency != null && invoice.originalCurrency != 'INR')) && (invoice.originalTotalAmount != null || extData.originalTotalAmount != null || extData.totalAmount != null)
                            ? '${invoice.originalCurrency ?? extData.currency ?? 'USD'} ${NumberFormat('#,##0.00').format(invoice.originalTotalAmount ?? extData.originalTotalAmount ?? extData.totalAmount ?? 0.0)}'
                            : null,
                        subtitle: 'Subtotal + Taxes + Surcharges',
                        icon: Icons.payments_outlined,
                        isBold: true,
                        isWarning: hasTotalMismatch,
                        onTap: () => setState(() => _isEditingFinancialSummary = true),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _buildSummaryCard(
                        context,
                        label: 'Net Vendor Payable',
                        value: currencyFormat.format(netPayable),
                        subtitle: isRcm
                            ? 'RCM Active: GST to Govt'
                            : 'Standard: Grand Total - TDS',
                        icon: Icons.check_circle_outline,
                        isHighlighted: !hasAnyMismatch,
                        isExceeded: isRcm,
                        onTap: () => setState(() => _isEditingFinancialSummary = true),
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 12),

                // Dedicated Prominent GST Breakdown Grid (CGST, SGST, IGST, CESS)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  decoration: BoxDecoration(
                    color: isDark ? const Color(0xFF0F172A).withOpacity(0.7) : const Color(0xFFF1F5F9),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: isDark ? const Color(0xFF334155) : const Color(0xFFCBD5E1),
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
                              const Icon(Icons.account_tree_outlined, size: 14, color: Color(0xFF0284C7)),
                              const SizedBox(width: 6),
                              Text(
                                'GST Breakdown & Statutory Tax Verification',
                                style: TextStyle(
                                  fontSize: 11.5,
                                  fontWeight: FontWeight.bold,
                                  color: isDark ? const Color(0xFF93C5FD) : const Color(0xFF0369A1),
                                ),
                              ),
                            ],
                          ),
                          Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(
                                'Total Tax: ${currencyFormat.format(totalTax)}',
                                style: TextStyle(
                                  fontSize: 11.5,
                                  fontWeight: FontWeight.bold,
                                  color: isDark ? Colors.white : const Color(0xFF0F172A),
                                ),
                              ),
                              const SizedBox(width: 8),
                              TextButton.icon(
                                onPressed: () async {
                                  final willBeInterState = !invProv.isInterState;
                                  final confirmed = await showFinancialConfirmationDialog(
                                    context: context,
                                    actionTitle: willBeInterState ? 'Switch to Inter-State (IGST)' : 'Switch to Intra-State (CGST + SGST)',
                                    reason: willBeInterState
                                        ? 'Consolidate taxes into Integrated GST (IGST) for interstate transactions.'
                                        : 'Split tax equally into Central GST (CGST) and State GST (SGST) for local supply.',
                                    formulaExplanation: willBeInterState ? 'IGST = 100% of GST rate' : 'CGST = 50% of GST rate, SGST = 50% of GST rate',
                                    comparisons: [
                                      FinancialFieldComparison(
                                        label: 'Supply Regime',
                                        currentValue: invProv.isInterState ? 'Inter-State (IGST)' : 'Intra-State (CGST+SGST)',
                                        proposedValue: willBeInterState ? 'Inter-State (IGST)' : 'Intra-State (CGST+SGST)',
                                        difference: 'Regime Switch',
                                        isDifferent: true,
                                      ),
                                      FinancialFieldComparison(
                                        label: 'Total GST Amount',
                                        currentValue: currencyFormat.format(totalTax),
                                        proposedValue: currencyFormat.format(totalTax),
                                        difference: '₹0.00 (Unchanged)',
                                        isDifferent: false,
                                      ),
                                    ],
                                  );

                                  if (confirmed && context.mounted) {
                                    invProv.applyConfirmedTaxSupplySwitch(targetInterState: willBeInterState);
                                    ScaffoldMessenger.of(context).showSnackBar(
                                      SnackBar(
                                        content: Text('Tax supply switched to ${willBeInterState ? "IGST" : "CGST+SGST"} after user confirmation.'),
                                        backgroundColor: const Color(0xFF0284C7),
                                        behavior: SnackBarBehavior.floating,
                                      ),
                                    );
                                  }
                                },
                                icon: const Icon(Icons.sync_alt_rounded, size: 11),
                                label: Text(
                                  invProv.isInterState
                                      ? 'Switch to CGST+SGST (50/50)'
                                      : 'Switch to IGST (Inter-State)',
                                  style: const TextStyle(fontSize: 10.5, fontWeight: FontWeight.bold),
                                ),
                                style: TextButton.styleFrom(
                                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                  visualDensity: VisualDensity.compact,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          // CGST
                          Expanded(
                            child: _buildTaxPill(
                              context,
                              label: 'CGST (Central Tax)',
                              amount: cgst,
                              color: const Color(0xFF2563EB),
                              currencyFormat: currencyFormat,
                              onTap: () => setState(() => _isEditingFinancialSummary = true),
                            ),
                          ),
                          const SizedBox(width: 8),
                          // SGST
                          Expanded(
                            child: _buildTaxPill(
                              context,
                              label: 'SGST / UTGST (State Tax)',
                              amount: sgst,
                              color: const Color(0xFF0891B2),
                              currencyFormat: currencyFormat,
                              onTap: () => setState(() => _isEditingFinancialSummary = true),
                            ),
                          ),
                          const SizedBox(width: 8),
                          // IGST
                          Expanded(
                            child: _buildTaxPill(
                              context,
                              label: 'IGST (Integrated Tax)',
                              amount: igst,
                              color: const Color(0xFF7C3AED),
                              currencyFormat: currencyFormat,
                              onTap: () => setState(() => _isEditingFinancialSummary = true),
                            ),
                          ),
                          const SizedBox(width: 8),
                          // CESS
                          Expanded(
                            child: _buildTaxPill(
                              context,
                              label: 'CESS (Compensation)',
                              amount: cess,
                              color: const Color(0xFFDB2777),
                              currencyFormat: currencyFormat,
                              onTap: () => setState(() => _isEditingFinancialSummary = true),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),

                // Commercial Adjustments or TDS if present
                if (discount > 0 || shipping > 0 || otherCharges > 0 || adjustment != 0 || roundOff != 0 || tdsAmount > 0) ...[
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      if (discount > 0 || shipping > 0 || otherCharges > 0 || adjustment != 0 || roundOff != 0) ...[
                        Expanded(
                          child: _buildSummaryCard(
                            context,
                            label: 'Net Adjustments',
                            value: (shipping + otherCharges + adjustment + roundOff - discount >= 0 ? '+ ' : '- ') +
                                currencyFormat.format((shipping + otherCharges + adjustment + roundOff - discount).abs()),
                            subtitle: [
                              if (discount > 0) 'Disc: -${currencyFormat.format(discount)}',
                              if (shipping > 0) 'Ship: +${currencyFormat.format(shipping)}',
                              if (otherCharges > 0) 'Other: +${currencyFormat.format(otherCharges)}',
                              if (adjustment != 0) 'Adj: ${currencyFormat.format(adjustment)}',
                              if (roundOff != 0) 'RO: ${currencyFormat.format(roundOff)}',
                            ].join(' • '),
                            icon: Icons.tune_outlined,
                            onTap: () => setState(() => _isEditingFinancialSummary = true),
                          ),
                        ),
                        const SizedBox(width: 10),
                      ],
                      if (tdsAmount > 0) ...[
                        Expanded(
                          child: _buildSummaryCard(
                            context,
                            label: 'TDS Withheld (-)',
                            value: '- ${currencyFormat.format(tdsAmount)}',
                            subtitle: 'Statutory Withholding Tax',
                            icon: Icons.percent_outlined,
                            isWarning: true,
                            onTap: () => setState(() => _isEditingFinancialSummary = true),
                          ),
                        ),
                      ],
                    ],
                  ),
                ],
              ],
            ),
          ),

          // When NOT editing: Visual Mathematical Settlement Pipeline Bar
          if (!_isEditingFinancialSummary) ...[
            Container(
              margin: const EdgeInsets.only(top: 12),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: theme.colorScheme.surfaceContainerHighest.withOpacity(0.18),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: theme.dividerColor.withOpacity(0.25)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.account_tree_outlined, size: 16, color: Color(0xFF0284C7)),
                  const SizedBox(width: 8),
                  Expanded(
                    child: SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: Row(
                        children: [
                          _buildFlowPill('Base', currencyFormat.format(subtotal), const Color(0xFF0284C7), isDark),
                          const Padding(
                            padding: EdgeInsets.symmetric(horizontal: 6),
                            child: Text('➕', style: TextStyle(fontSize: 11)),
                          ),
                          _buildFlowPill('GST Taxes', currencyFormat.format(totalTax), const Color(0xFF6366F1), isDark),
                          if (discount > 0) ...[
                            const Padding(
                              padding: EdgeInsets.symmetric(horizontal: 6),
                              child: Text('➖', style: TextStyle(fontSize: 11)),
                            ),
                            _buildFlowPill('Discount', currencyFormat.format(discount), Colors.orange, isDark),
                          ],
                          if (shipping > 0) ...[
                            const Padding(
                              padding: EdgeInsets.symmetric(horizontal: 6),
                              child: Text('➕', style: TextStyle(fontSize: 11)),
                            ),
                            _buildFlowPill('Freight', currencyFormat.format(shipping), Colors.blueGrey, isDark),
                          ],
                          const Padding(
                            padding: EdgeInsets.symmetric(horizontal: 6),
                            child: Text('🟰', style: TextStyle(fontSize: 11)),
                          ),
                          _buildFlowPill('Grand Total', currencyFormat.format(grandTotal), const Color(0xFF0F172A), isDark, isBold: true),
                          if (tdsAmount > 0) ...[
                            const Padding(
                              padding: EdgeInsets.symmetric(horizontal: 6),
                              child: Text('➖', style: TextStyle(fontSize: 11)),
                            ),
                            _buildFlowPill('TDS Withheld', currencyFormat.format(tdsAmount), const Color(0xFFD97706), isDark),
                          ],
                          const Padding(
                            padding: EdgeInsets.symmetric(horizontal: 6),
                            child: Text('➔', style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold)),
                          ),
                          _buildFlowPill('Net Settlement', currencyFormat.format(netPayable), const Color(0xFF10B981), isDark, isBold: true, isHighlight: true),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  TextButton.icon(
                    onPressed: () => setState(() => _isEditingFinancialSummary = true),
                    icon: const Icon(Icons.edit_note_rounded, size: 14),
                    label: const Text('Adjust Figures', style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.bold)),
                    style: TextButton.styleFrom(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      visualDensity: VisualDensity.compact,
                    ),
                  ),
                ],
              ),
            ),
          ],

          // When Editing: Granular Field Editors for Base, Taxes, Freight & Final Adjustments
          if (_isEditingFinancialSummary) ...[
            const SizedBox(height: 16),

            // Direct Financial Base & Tax Breakdown Editors
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: theme.colorScheme.surfaceContainerHighest.withOpacity(0.18),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: const Color(0xFF0284C7).withOpacity(0.4)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Row(
                        children: [
                          const Icon(Icons.edit_note_rounded, size: 16, color: Color(0xFF0284C7)),
                          const SizedBox(width: 6),
                          Text(
                            'Direct Subtotal & Statutory Tax Fields',
                            style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.bold, color: isDark ? Colors.white : const Color(0xFF0F172A)),
                          ),
                        ],
                      ),
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          TextButton.icon(
                            onPressed: () async {
                              final confirmed = await showFinancialConfirmationDialog(
                                context: context,
                                actionTitle: 'Confirm Tax Supply Type Split (CGST + SGST)',
                                reason: 'Convert interstate tax structure (IGST) to intra-state split (50% CGST + 50% SGST) across line items.',
                                formulaExplanation: 'Line GST Rate ÷ 2 split equally between CGST and SGST',
                                comparisons: [
                                  FinancialFieldComparison(
                                    label: 'Tax Supply Regime',
                                    currentValue: 'Inter-State (IGST)',
                                    proposedValue: 'Intra-State (50% CGST + 50% SGST)',
                                    difference: 'Structure Change',
                                    isDifferent: true,
                                  ),
                                  FinancialFieldComparison(
                                    label: 'IGST Amount',
                                    currentValue: currencyFormat.format(igst),
                                    proposedValue: '₹0.00',
                                    difference: '-${currencyFormat.format(igst)}',
                                    isDifferent: igst > 0,
                                  ),
                                  FinancialFieldComparison(
                                    label: 'CGST + SGST (Combined)',
                                    currentValue: currencyFormat.format(cgst + sgst),
                                    proposedValue: currencyFormat.format(totalTax),
                                    difference: '+${currencyFormat.format(totalTax - (cgst + sgst))}',
                                    isDifferent: true,
                                  ),
                                ],
                              );

                              if (confirmed && context.mounted) {
                                invProv.applyConfirmedTaxSupplySwitch(targetInterState: false);
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(
                                    content: Text('Tax split updated to Intra-State (CGST + SGST) after user confirmation.'),
                                    backgroundColor: Color(0xFF0284C7),
                                    behavior: SnackBarBehavior.floating,
                                  ),
                                );
                              }
                            },
                            icon: const Icon(Icons.call_split, size: 13),
                            label: const Text('Split 50% CGST/SGST', style: TextStyle(fontSize: 11)),
                            style: TextButton.styleFrom(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4), visualDensity: VisualDensity.compact),
                          ),
                          const SizedBox(width: 4),
                          TextButton.icon(
                            onPressed: () async {
                              final confirmed = await showFinancialConfirmationDialog(
                                context: context,
                                actionTitle: 'Confirm Full Recalculation from Line Items',
                                reason: 'Recalculate statutory taxes, subtotal, and grand total strictly from line items quantity, rate, and tax rates.',
                                formulaExplanation: 'Aggregates line-by-line taxable amount + GST + Cess to recompute invoice summary.',
                                comparisons: [
                                  FinancialFieldComparison(
                                    label: 'Taxable Subtotal',
                                    currentValue: currencyFormat.format(subtotal),
                                    proposedValue: currencyFormat.format(lineItemsSum),
                                    difference: (lineItemsSum - subtotal).abs() > 0.01
                                        ? (lineItemsSum >= subtotal ? '+${currencyFormat.format(lineItemsSum - subtotal)}' : '-${currencyFormat.format(subtotal - lineItemsSum)}')
                                        : '₹0.00',
                                    isDifferent: (lineItemsSum - subtotal).abs() > 0.01,
                                  ),
                                  FinancialFieldComparison(
                                    label: 'Total Amount',
                                    currentValue: currencyFormat.format(extractedGrandTotal ?? 0),
                                    proposedValue: currencyFormat.format(calculatedGrandTotal),
                                    difference: ((calculatedGrandTotal - (extractedGrandTotal ?? 0)).abs() > 0.01)
                                        ? (calculatedGrandTotal >= (extractedGrandTotal ?? 0)
                                            ? '+${currencyFormat.format(calculatedGrandTotal - (extractedGrandTotal ?? 0))}'
                                            : '-${currencyFormat.format((extractedGrandTotal ?? 0) - calculatedGrandTotal)}')
                                        : '₹0.00',
                                    isDifferent: ((calculatedGrandTotal - (extractedGrandTotal ?? 0)).abs() > 0.01),
                                  ),
                                ],
                              );

                              if (confirmed && context.mounted) {
                                invProv.applyConfirmedFullRecalculation();
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(
                                    content: Text('Invoice totals recalculated from line items after user confirmation.'),
                                    backgroundColor: Color(0xFF0284C7),
                                    behavior: SnackBarBehavior.floating,
                                  ),
                                );
                              }
                            },
                            icon: const Icon(Icons.sync, size: 13),
                            label: const Text('Sync with Line Items', style: TextStyle(fontSize: 11)),
                            style: TextButton.styleFrom(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4), visualDensity: VisualDensity.compact),
                          ),
                        ],
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  // Row 1: Taxable Subtotal, CGST, SGST, IGST, CESS, Total Tax
                  Row(
                    children: [
                      // Taxable Subtotal
                      Expanded(
                        flex: 2,
                        child: TextFormField(
                          key: ValueKey('fin_taxable_${extData.taxableAmount}'),
                          initialValue: extData.taxableAmount != null ? extData.taxableAmount.toString() : '',
                          decoration: const InputDecoration(
                            labelText: 'Taxable Subtotal (₹)',
                            border: OutlineInputBorder(),
                            contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                            isDense: true,
                            prefixIcon: Icon(Icons.account_balance_wallet_outlined, size: 15),
                          ),
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          onChanged: (v) {
                            extData.taxableAmount = double.tryParse(v);
                            extData.subtotal = extData.taxableAmount;
                            invProv.updateFinancialSummary(taxableAmount: extData.taxableAmount);
                          },
                        ),
                      ),
                      const SizedBox(width: 8),
                      // CGST
                      Expanded(
                        flex: 2,
                        child: TextFormField(
                          key: ValueKey('fin_cgst_${extData.cgstAmount}'),
                          initialValue: (extData.cgstAmount ?? 0) > 0 ? extData.cgstAmount.toString() : '',
                          decoration: const InputDecoration(
                            labelText: 'CGST (₹)',
                            border: OutlineInputBorder(),
                            contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                            isDense: true,
                          ),
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          onChanged: (v) {
                            extData.cgstAmount = double.tryParse(v);
                            final c = extData.cgstAmount ?? 0.0;
                            final s = extData.sgstAmount ?? 0.0;
                            final i = extData.igstAmount ?? 0.0;
                            final cs = extData.cessAmount ?? 0.0;
                            extData.taxTotal = c + s + i + cs;
                            invProv.updateFinancialSummary(cgstAmount: extData.cgstAmount, taxTotal: extData.taxTotal);
                          },
                        ),
                      ),
                      const SizedBox(width: 8),
                      // SGST
                      Expanded(
                        flex: 2,
                        child: TextFormField(
                          key: ValueKey('fin_sgst_${extData.sgstAmount}'),
                          initialValue: (extData.sgstAmount ?? 0) > 0 ? extData.sgstAmount.toString() : '',
                          decoration: const InputDecoration(
                            labelText: 'SGST / UTGST (₹)',
                            border: OutlineInputBorder(),
                            contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                            isDense: true,
                          ),
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          onChanged: (v) {
                            extData.sgstAmount = double.tryParse(v);
                            final c = extData.cgstAmount ?? 0.0;
                            final s = extData.sgstAmount ?? 0.0;
                            final i = extData.igstAmount ?? 0.0;
                            final cs = extData.cessAmount ?? 0.0;
                            extData.taxTotal = c + s + i + cs;
                            invProv.updateFinancialSummary(sgstAmount: extData.sgstAmount, taxTotal: extData.taxTotal);
                          },
                        ),
                      ),
                      const SizedBox(width: 8),
                      // IGST
                      Expanded(
                        flex: 2,
                        child: TextFormField(
                          key: ValueKey('fin_igst_${extData.igstAmount}'),
                          initialValue: (extData.igstAmount ?? 0) > 0 ? extData.igstAmount.toString() : '',
                          decoration: const InputDecoration(
                            labelText: 'IGST (₹)',
                            border: OutlineInputBorder(),
                            contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                            isDense: true,
                          ),
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          onChanged: (v) {
                            extData.igstAmount = double.tryParse(v);
                            final c = extData.cgstAmount ?? 0.0;
                            final s = extData.sgstAmount ?? 0.0;
                            final i = extData.igstAmount ?? 0.0;
                            final cs = extData.cessAmount ?? 0.0;
                            extData.taxTotal = c + s + i + cs;
                            invProv.updateFinancialSummary(igstAmount: extData.igstAmount, taxTotal: extData.taxTotal);
                          },
                        ),
                      ),
                      const SizedBox(width: 8),
                      // CESS
                      Expanded(
                        flex: 1,
                        child: TextFormField(
                          key: ValueKey('fin_cess_${extData.cessAmount}'),
                          initialValue: (extData.cessAmount ?? 0) > 0 ? extData.cessAmount.toString() : '',
                          decoration: const InputDecoration(
                            labelText: 'CESS (₹)',
                            border: OutlineInputBorder(),
                            contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                            isDense: true,
                          ),
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          onChanged: (v) {
                            extData.cessAmount = double.tryParse(v);
                            final c = extData.cgstAmount ?? 0.0;
                            final s = extData.sgstAmount ?? 0.0;
                            final i = extData.igstAmount ?? 0.0;
                            final cs = extData.cessAmount ?? 0.0;
                            extData.taxTotal = c + s + i + cs;
                            invProv.updateFinancialSummary(cessAmount: extData.cessAmount, taxTotal: extData.taxTotal);
                          },
                        ),
                      ),
                      const SizedBox(width: 8),
                      // Total Tax
                      Expanded(
                        flex: 2,
                        child: TextFormField(
                          key: ValueKey('fin_taxtot_${extData.taxTotal}'),
                          initialValue: (extData.taxTotal ?? 0) > 0 ? extData.taxTotal.toString() : '',
                          decoration: const InputDecoration(
                            labelText: 'Total GST Tax (₹)',
                            border: OutlineInputBorder(),
                            contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                            isDense: true,
                            prefixIcon: Icon(Icons.receipt_long, size: 15),
                          ),
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          onChanged: (v) {
                            extData.taxTotal = double.tryParse(v);
                            invProv.updateFinancialSummary(taxTotal: extData.taxTotal);
                          },
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),

            const SizedBox(height: 12),

            // Editable Surcharges & Adjustments Row (Discount, Shipping, Other Charges, Adjustment, Round Off, Grand Total)
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: theme.colorScheme.surfaceContainerHighest.withOpacity(0.15),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: theme.dividerColor.withOpacity(0.3)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Row(
                        children: [
                          Icon(Icons.tune_outlined, size: 15, color: theme.textTheme.bodySmall?.color),
                          const SizedBox(width: 6),
                          Text(
                            'Commercial Adjustments, Freight, Rounding & Final Total',
                            style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: theme.textTheme.bodySmall?.color),
                          ),
                        ],
                      ),
                      Text(
                        'Live dynamic recalculation enabled',
                        style: TextStyle(fontSize: 10, color: theme.textTheme.bodySmall?.color?.withOpacity(0.7)),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      // Discount
                      Expanded(
                        child: TextFormField(
                          key: ValueKey('fin_disc_${extData.discountTotal}'),
                          initialValue: (extData.discountTotal ?? 0) > 0 ? extData.discountTotal.toString() : '',
                          decoration: const InputDecoration(
                            labelText: 'Discount (-)',
                            border: OutlineInputBorder(),
                            contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                            isDense: true,
                          ),
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          onChanged: (v) {
                            extData.discountTotal = double.tryParse(v);
                            invProv.updateFinancialSummary(discountTotal: extData.discountTotal);
                          },
                        ),
                      ),
                      const SizedBox(width: 8),
                      // Shipping / Freight
                      Expanded(
                        child: TextFormField(
                          key: ValueKey('fin_ship_${extData.shippingCharges}'),
                          initialValue: (extData.shippingCharges ?? 0) > 0 ? extData.shippingCharges.toString() : '',
                          decoration: const InputDecoration(
                            labelText: 'Shipping / Freight (+)',
                            border: OutlineInputBorder(),
                            contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                            isDense: true,
                          ),
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          onChanged: (v) {
                            extData.shippingCharges = double.tryParse(v);
                            invProv.updateFinancialSummary(shippingCharges: extData.shippingCharges);
                          },
                        ),
                      ),
                      const SizedBox(width: 8),
                      // Other Charges
                      Expanded(
                        child: TextFormField(
                          key: ValueKey('fin_other_${extData.otherCharges}'),
                          initialValue: (extData.otherCharges ?? 0) > 0 ? extData.otherCharges.toString() : '',
                          decoration: const InputDecoration(
                            labelText: 'Other Charges (+)',
                            border: OutlineInputBorder(),
                            contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                            isDense: true,
                          ),
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          onChanged: (v) {
                            extData.otherCharges = double.tryParse(v);
                            invProv.updateFinancialSummary(otherCharges: extData.otherCharges);
                          },
                        ),
                      ),
                      const SizedBox(width: 8),
                      // Adjustment
                      Expanded(
                        child: TextFormField(
                          key: ValueKey('fin_adj_${extData.adjustment}'),
                          initialValue: extData.adjustment != null && extData.adjustment != 0 ? extData.adjustment.toString() : '',
                          decoration: const InputDecoration(
                            labelText: 'Adjustment (+/-)',
                            border: OutlineInputBorder(),
                            contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                            isDense: true,
                          ),
                          keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true),
                          onChanged: (v) {
                            extData.adjustment = double.tryParse(v);
                            invProv.updateFinancialSummary(adjustment: extData.adjustment);
                          },
                        ),
                      ),
                      const SizedBox(width: 8),
                      // Round Off
                      Expanded(
                        child: TextFormField(
                          key: ValueKey('fin_ro_${extData.roundOff}'),
                          initialValue: extData.roundOff != null && extData.roundOff != 0 ? extData.roundOff.toString() : '',
                          decoration: const InputDecoration(
                            labelText: 'Round Off (+/-)',
                            border: OutlineInputBorder(),
                            contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                            isDense: true,
                          ),
                          keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true),
                          onChanged: (v) {
                            extData.roundOff = double.tryParse(v);
                            invProv.updateFinancialSummary(roundOff: extData.roundOff);
                          },
                        ),
                      ),
                      const SizedBox(width: 8),
                      // Invoice Grand Total
                      Expanded(
                        flex: 2,
                        child: TextFormField(
                          key: ValueKey('fin_total_${extData.totalAmount}'),
                          initialValue: extData.totalAmount != null ? extData.totalAmount.toString() : '',
                          decoration: InputDecoration(
                            labelText: 'Invoice Grand Total (₹)',
                            border: const OutlineInputBorder(),
                            contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                            isDense: true,
                            prefixIcon: const Icon(Icons.payments_outlined, size: 15, color: Color(0xFF10B981)),
                            focusedBorder: OutlineInputBorder(
                              borderSide: BorderSide(color: hasTotalMismatch ? const Color(0xFFF59E0B) : const Color(0xFF10B981), width: 2),
                            ),
                          ),
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          style: const TextStyle(fontWeight: FontWeight.bold),
                          onChanged: (v) {
                            extData.totalAmount = double.tryParse(v);
                            invProv.updateFinancialSummary(totalAmount: extData.totalAmount);
                          },
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),

            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                ElevatedButton.icon(
                  onPressed: () {
                    setState(() {
                      _isEditingFinancialSummary = false;
                    });
                  },
                  icon: const Icon(Icons.check, size: 15),
                  label: const Text('Done & Apply Figures'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF10B981),
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    textStyle: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }



  Widget _buildSummaryCard(
    BuildContext context, {
    required String label,
    required String value,
    String? foreignValue,
    required String subtitle,
    required IconData icon,
    bool isBold = false,
    bool isHighlighted = false,
    bool isWarning = false,
    bool isExceeded = false,
    VoidCallback? onTap,
  }) {
    final theme = Theme.of(context);
    final borderColor = isHighlighted
        ? const Color(0xFF10B981).withOpacity(0.5)
        : (isWarning
            ? Colors.amber.withOpacity(0.5)
            : theme.dividerColor.withOpacity(0.3));

    final bgColor = isHighlighted
        ? const Color(0xFF10B981).withOpacity(0.08)
        : (isWarning
            ? Colors.amber.withOpacity(0.08)
            : theme.colorScheme.surfaceContainerHighest.withOpacity(0.2));

    final valColor = isHighlighted
        ? const Color(0xFF10B981)
        : (isWarning
            ? Colors.amber.shade300
            : theme.textTheme.bodyLarge?.color);

    final cardContent = Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: borderColor),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Icon(
                icon,
                size: 14,
                color: isHighlighted
                    ? const Color(0xFF10B981)
                    : (isWarning ? Colors.amber : theme.textTheme.bodySmall?.color),
              ),
              const SizedBox(width: 5),
              Expanded(
                child: Text(
                  label,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: theme.textTheme.bodySmall?.color,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              if (onTap != null) ...[
                const SizedBox(width: 4),
                Icon(
                  Icons.edit_outlined,
                  size: 11,
                  color: theme.textTheme.bodySmall?.color?.withOpacity(0.4),
                ),
              ],
            ],
          ),
          const SizedBox(height: 5),
          Wrap(
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 6,
            runSpacing: 2,
            children: [
              Text(
                value,
                style: TextStyle(
                  fontSize: isHighlighted ? 15 : (isBold ? 14 : 13),
                  fontWeight: FontWeight.bold,
                  color: valColor,
                ),
              ),
              if (foreignValue != null && foreignValue.isNotEmpty) ...[
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
                  decoration: BoxDecoration(
                    color: const Color(0xFF0284C7).withOpacity(0.15),
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(color: const Color(0xFF38BDF8).withOpacity(0.4), width: 0.8),
                  ),
                  child: Text(
                    foreignValue,
                    style: const TextStyle(
                      fontSize: 9.5,
                      fontWeight: FontWeight.w700,
                      color: Color(0xFF0284C7),
                    ),
                  ),
                ),
              ],
            ],
          ),
          if (subtitle.isNotEmpty) ...[
            const SizedBox(height: 3),
            Text(
              subtitle,
              style: TextStyle(
                fontSize: 10,
                color: theme.textTheme.bodySmall?.color?.withOpacity(0.7),
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ],
      ),
    );

    if (onTap != null) {
      return InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: cardContent,
      );
    }
    return cardContent;
  }

  Widget _buildTaxPill(
    BuildContext context, {
    required String label,
    required double amount,
    required Color color,
    required NumberFormat currencyFormat,
    VoidCallback? onTap,
  }) {
    final isZero = amount == 0.0;
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(6),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        decoration: BoxDecoration(
          color: isZero
              ? (isDark ? Colors.white.withOpacity(0.02) : Colors.white.withOpacity(0.7))
              : color.withOpacity(isDark ? 0.18 : 0.08),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(
            color: isZero
                ? (isDark ? Colors.white.withOpacity(0.08) : Colors.black.withOpacity(0.08))
                : color.withOpacity(isDark ? 0.5 : 0.35),
            width: isZero ? 1 : 1.5,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                Container(
                  width: 7,
                  height: 7,
                  decoration: BoxDecoration(
                    color: isZero ? Colors.grey.shade400 : color,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 5),
                Expanded(
                  child: Text(
                    label,
                    style: TextStyle(
                      fontSize: 10.5,
                      fontWeight: FontWeight.w600,
                      color: isZero
                          ? (isDark ? Colors.grey.shade400 : Colors.grey.shade600)
                          : (isDark ? color.withOpacity(0.9) : const Color(0xFF0F172A)),
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              currencyFormat.format(amount),
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.bold,
                color: isZero
                    ? (isDark ? Colors.grey.shade500 : Colors.grey.shade400)
                    : (isDark ? Colors.white : const Color(0xFF0F172A)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFlowPill(
    String label,
    String value,
    Color color,
    bool isDark, {
    bool isBold = false,
    bool isHighlight = false,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: isHighlight
            ? color.withValues(alpha: isDark ? 0.25 : 0.12)
            : (isDark ? Colors.white.withValues(alpha: 0.04) : Colors.white),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(
          color: isHighlight
              ? color.withValues(alpha: 0.8)
              : (isDark ? Colors.white.withValues(alpha: 0.12) : color.withValues(alpha: 0.25)),
          width: isHighlight ? 1.5 : 1.0,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(
              color: color,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 6),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                label.toUpperCase(),
                style: TextStyle(
                  fontSize: 8.5,
                  letterSpacing: 0.5,
                  fontWeight: FontWeight.w700,
                  color: isDark ? Colors.grey.shade400 : Colors.grey.shade600,
                ),
              ),
              Text(
                value,
                style: TextStyle(
                  fontSize: isHighlight ? 12.5 : 11.5,
                  fontWeight: isBold || isHighlight ? FontWeight.w800 : FontWeight.w600,
                  color: isHighlight
                      ? (isDark ? Colors.white : color)
                      : (isDark ? Colors.white : const Color(0xFF0F172A)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  PreferredSizeWidget _buildWorkspaceAppBar(BuildContext context, Invoice invoice, InvoiceProvider invProv) {
    final theme = Theme.of(context);
    final isExported = invoice.displayStatus == 'exported';
    final isApproved = invoice.displayStatus == 'approved';

    return AppBar(
      titleSpacing: 0,
      title: Row(
        children: [
          const SizedBox(width: 8),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(
                    invoice.extractedData?.invoiceNumber ?? 'Invoice #${invoice.id}',
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                  ),
                  const SizedBox(width: 10),
                  StatusBadge(status: invoice.displayStatus),
                ],
              ),
              Text(
                invoice.extractedData?.vendorName ?? invoice.originalFilename ?? 'Vendor Invoice',
                style: theme.textTheme.bodySmall?.copyWith(fontSize: 12),
              ),
            ],
          ),
        ],
      ),
      actions: [
        if (widget.isCustomerMode || widget.isReadOnly) ...[
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            margin: const EdgeInsets.symmetric(vertical: 10),
            decoration: BoxDecoration(
              color: const Color(0xFF6366F1).withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: const Color(0xFF6366F1).withValues(alpha: 0.3)),
            ),
            child: const Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.visibility_rounded, size: 14, color: Color(0xFF6366F1)),
                SizedBox(width: 5),
                Text('Customer View', style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.bold, color: Color(0xFF6366F1))),
              ],
            ),
          ),
          const SizedBox(width: 8),
        ],
        // Toggle PDF Preview Button
        IconButton(
          tooltip: _showDocumentPreview ? 'Hide Document Preview' : 'Show Document Preview',
          icon: Icon(_showDocumentPreview ? Icons.vertical_split : Icons.picture_as_pdf_outlined),
          onPressed: () {
            setState(() => _showDocumentPreview = !_showDocumentPreview);
          },
        ),

        if (!widget.isCustomerMode && !widget.isReadOnly) ...[
          // Create Account in Zoho COA Dialog
          IconButton(
            tooltip: 'Create Account in Zoho COA',
            icon: const Icon(Icons.add_card_outlined, color: Colors.blueAccent),
            onPressed: () {
              showDialog(
                context: context,
                builder: (ctx) => CreateCoaDialog(
                  onConfirm: (name, type, code, desc) async {
                    final ok = await invProv.createZohoAccount(
                      accountName: name,
                      accountType: type,
                      accountCode: code,
                      description: desc,
                    );
                    if (context.mounted && ok) {
                      await context.read<IntegrationProvider>().fetchZohoMasterData();
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(content: Text('Account "$name" created in Zoho Books COA and synced!')),
                      );
                    }
                  },
                ),
              );
            },
          ),

          // Reject Button
          if (!isApproved && !isExported)
          OutlinedButton.icon(
            onPressed: invProv.isRejecting
                ? null
                : () {
                    showDialog(
                      context: context,
                      builder: (ctx) => RejectInvoiceDialog(
                        onConfirm: (reason) async {
                          final ok = await invProv.rejectInvoice(reason);
                          if (context.mounted && ok) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text('Invoice rejected with audit reason')),
                            );
                          }
                        },
                      ),
                    );
                  },
            icon: const Icon(Icons.close, size: 16, color: Colors.redAccent),
            label: const Text('Reject', style: TextStyle(color: Colors.redAccent)),
            style: OutlinedButton.styleFrom(
              side: const BorderSide(color: Colors.redAccent),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            ),
          ),
        const SizedBox(width: 8),

        // Save Draft Button
        OutlinedButton.icon(
          onPressed: invProv.isSaving
              ? null
              : () async {
                  final ok = await invProv.saveDraft();
                  if (context.mounted && ok) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Draft modifications saved successfully')),
                    );
                  }
                },
          icon: invProv.isSaving
              ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2))
              : const Icon(Icons.save_outlined, size: 16),
          label: const Text('Save Draft'),
        ),
        const SizedBox(width: 8),

        // Master Approve & Export / Resync to Zoho Button
        ElevatedButton.icon(
          onPressed: invProv.isExporting
              ? null
              : () async {
                  final ok = await invProv.exportToZoho();
                  if (context.mounted && ok) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(
                          isExported
                              ? 'Invoice successfully resynced and updated in Zoho Books!'
                              : 'Invoice successfully approved and exported to Zoho Books!',
                        ),
                        backgroundColor: const Color(0xFF10B981),
                      ),
                    );
                  }
                },
          icon: invProv.isExporting
              ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
              : Icon(isExported ? Icons.sync_rounded : (isApproved ? Icons.cloud_upload_outlined : Icons.check_circle_outline), size: 16),
          label: Text(isExported ? 'Resync with Zoho' : (isApproved ? 'Export Bill to Zoho' : 'Approve & Export')),
          style: ElevatedButton.styleFrom(
            backgroundColor: isExported ? const Color(0xFF6366F1) : (isApproved ? const Color(0xFF10B981) : Colors.blueAccent),
            foregroundColor: Colors.white,
          ),
        ),
        ],
        const SizedBox(width: 16),
      ],
    );
  }

  Widget _buildSectionJumpBar(BuildContext context) {
    final sections = [
      {'label': '1. Header & Parties', 'icon': Icons.business_outlined},
      {'label': '2. Line Items', 'icon': Icons.receipt_long_outlined},
      {'label': '3. Financial Summary', 'icon': Icons.calculate_outlined},
      {'label': '4. GST & RCM', 'icon': Icons.account_balance_outlined},
      {'label': '5. TDS Assessment', 'icon': Icons.percent_outlined},
      {'label': '6. ITC Compliance', 'icon': Icons.verified_outlined},
      {'label': '7. Bank Settlement', 'icon': Icons.account_balance_wallet_outlined},
      {'label': '8. GL Journal', 'icon': Icons.menu_book_outlined},
    ];
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      physics: const BouncingScrollPhysics(),
      child: Row(
        children: List.generate(sections.length, (idx) {
          final isSelected = _activeSectionIndex == idx;
          final sec = sections[idx];
          return Padding(
            padding: const EdgeInsets.only(right: 8),
            child: FilterChip(
              avatar: Icon(
                sec['icon'] as IconData,
                size: 15,
                color: isSelected
                    ? Colors.white
                    : (isDark ? Colors.blue.shade300 : const Color(0xFF4F46E5)),
              ),
              label: Text(
                sec['label'] as String,
                style: TextStyle(
                  fontSize: 12.5,
                  fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                  color: isSelected
                      ? Colors.white
                      : (isDark ? Colors.white70 : const Color(0xFF1E293B)),
                ),
              ),
              selected: isSelected,
              selectedColor: const Color(0xFF0284C7),
              showCheckmark: false,
              backgroundColor: isDark ? const Color(0xFF1E293B) : Colors.white,
              side: BorderSide(
                color: isSelected
                    ? const Color(0xFF0284C7)
                    : (isDark ? const Color(0xFF334155) : const Color(0xFFCBD5E1)),
                width: isSelected ? 1.5 : 1,
              ),
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
              onSelected: (_) => _scrollToSection(idx),
            ),
          );
        }),
      ),
    );
  }

  Widget _buildHeaderSection(BuildContext context, ExtractedInvoiceData extData, InvoiceProvider invProv) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return GlassCard(
      key: ValueKey('hdr_${extData.vendorName}_${extData.invoiceNumber}_${extData.vendorGstin}_${extData.totalAmount}_${extData.vendorPhone}_${extData.vendorEmail}'),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.business_outlined, color: Colors.blueAccent, size: 20),
                const SizedBox(width: 8),
                Text('Invoice Header & Tax Identifiers', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Vendor Details
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Vendor Information', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.blue.shade300)),
                      const SizedBox(height: 8),
                      TextFormField(
                        key: ValueKey('vnd_name_${extData.vendorName}'),
                        initialValue: extData.vendorName ?? '',
                        decoration: const InputDecoration(labelText: 'Vendor Legal Name', border: OutlineInputBorder()),
                        onChanged: (v) => extData.vendorName = v,
                      ),
                      const SizedBox(height: 10),
                      TextFormField(
                        key: ValueKey('vnd_gstin_${extData.vendorGstin}'),
                        initialValue: extData.vendorGstin ?? '',
                        decoration: const InputDecoration(labelText: 'Vendor GSTIN', border: OutlineInputBorder()),
                        onChanged: (v) => extData.vendorGstin = v,
                      ),
                      const SizedBox(height: 10),
                      TextFormField(
                        key: ValueKey('vnd_pan_${extData.vendorPan}'),
                        initialValue: extData.vendorPan ?? '',
                        decoration: const InputDecoration(labelText: 'Vendor PAN', border: OutlineInputBorder()),
                        onChanged: (v) => extData.vendorPan = v,
                      ),
                      const SizedBox(height: 10),
                      TextFormField(
                        key: ValueKey('vnd_phone_${extData.vendorPhone}'),
                        initialValue: extData.vendorPhone ?? '',
                        decoration: const InputDecoration(labelText: 'Vendor Phone / Mobile', border: OutlineInputBorder(), prefixIcon: Icon(Icons.phone_outlined, size: 16)),
                        onChanged: (v) => extData.vendorPhone = v,
                      ),
                      const SizedBox(height: 10),
                      TextFormField(
                        key: ValueKey('vnd_email_${extData.vendorEmail}'),
                        initialValue: extData.vendorEmail ?? '',
                        decoration: const InputDecoration(labelText: 'Vendor Email', border: OutlineInputBorder(), prefixIcon: Icon(Icons.email_outlined, size: 16)),
                        onChanged: (v) => extData.vendorEmail = v,
                      ),
                      const SizedBox(height: 10),
                      TextFormField(
                        key: ValueKey('vnd_addr_${extData.vendorAddress}'),
                        initialValue: extData.vendorAddress ?? '',
                        maxLines: 2,
                        decoration: const InputDecoration(labelText: 'Vendor Registered Address', border: OutlineInputBorder()),
                        onChanged: (v) => extData.vendorAddress = v,
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 16),
                // Customer & Place of Supply
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Customer & Delivery', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.teal.shade300)),
                      const SizedBox(height: 8),
                      TextFormField(
                        key: ValueKey('cust_name_${extData.customerName}'),
                        initialValue: extData.customerName ?? '',
                        decoration: const InputDecoration(labelText: 'Customer / Entity Name', border: OutlineInputBorder()),
                        onChanged: (v) => extData.customerName = v,
                      ),
                      const SizedBox(height: 10),
                      TextFormField(
                        key: ValueKey('cust_gstin_${extData.customerGstin}'),
                        initialValue: extData.customerGstin ?? '',
                        decoration: const InputDecoration(labelText: 'Customer GSTIN', border: OutlineInputBorder()),
                        onChanged: (v) => extData.customerGstin = v,
                      ),
                      const SizedBox(height: 10),
                      TextFormField(
                        key: ValueKey('cust_pan_${extData.customerPan}'),
                        initialValue: extData.customerPan ?? '',
                        decoration: const InputDecoration(labelText: 'Customer PAN', border: OutlineInputBorder()),
                        onChanged: (v) => extData.customerPan = v,
                      ),
                      const SizedBox(height: 10),
                      TextFormField(
                        key: ValueKey('cust_addr_${extData.customerAddress}'),
                        initialValue: extData.customerAddress ?? '',
                        maxLines: 3,
                        decoration: const InputDecoration(labelText: 'Customer Billing / Shipping Address', border: OutlineInputBorder()),
                        onChanged: (v) => extData.customerAddress = v,
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 16),
                // Invoice Details
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Document Reference', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.purple.shade300)),
                      const SizedBox(height: 8),
                      TextFormField(
                        key: ValueKey('inv_num_${extData.invoiceNumber}'),
                        initialValue: extData.invoiceNumber ?? '',
                        decoration: const InputDecoration(labelText: 'Invoice Number', border: OutlineInputBorder()),
                        onChanged: (v) => extData.invoiceNumber = v,
                      ),
                      const SizedBox(height: 10),
                      Row(
                        children: [
                          Expanded(
                            child: TextFormField(
                              key: ValueKey('inv_date_${extData.invoiceDate}'),
                              initialValue: extData.invoiceDate ?? '',
                              decoration: InputDecoration(
                                labelText: 'Invoice Date',
                                border: const OutlineInputBorder(),
                                suffixIcon: IconButton(
                                  icon: const Icon(Icons.calendar_month, size: 16),
                                  onPressed: () async {
                                    final now = DateTime.now();
                                    final picked = await showDatePicker(
                                      context: context,
                                      initialDate: now,
                                      firstDate: DateTime(2020),
                                      lastDate: DateTime(2035),
                                    );
                                    if (picked != null) {
                                      final formatted = DateFormat('yyyy-MM-dd').format(picked);
                                      extData.invoiceDate = formatted;
                                      invProv.updateFinancialSummary();
                                    }
                                  },
                                ),
                              ),
                              onChanged: (v) => extData.invoiceDate = v,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: TextFormField(
                              key: ValueKey('inv_due_${extData.dueDate}'),
                              initialValue: extData.dueDate ?? '',
                              decoration: InputDecoration(
                                labelText: 'Due Date',
                                border: const OutlineInputBorder(),
                                suffixIcon: IconButton(
                                  icon: const Icon(Icons.event_available, size: 16),
                                  onPressed: () async {
                                    final now = DateTime.now();
                                    final picked = await showDatePicker(
                                      context: context,
                                      initialDate: now,
                                      firstDate: DateTime(2020),
                                      lastDate: DateTime(2035),
                                    );
                                    if (picked != null) {
                                      final formatted = DateFormat('yyyy-MM-dd').format(picked);
                                      extData.dueDate = formatted;
                                      invProv.updateFinancialSummary();
                                    }
                                  },
                                ),
                              ),
                              onChanged: (v) => extData.dueDate = v,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Row(
                        children: [
                          Expanded(
                            child: TextFormField(
                              key: ValueKey('inv_curr_${extData.currency}'),
                              initialValue: extData.currency ?? 'INR',
                              decoration: const InputDecoration(labelText: 'Currency', border: OutlineInputBorder(), prefixIcon: Icon(Icons.currency_rupee, size: 16)),
                              onChanged: (v) => extData.currency = v,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: TextFormField(
                              key: ValueKey('inv_terms_${extData.paymentTerms}'),
                              initialValue: extData.paymentTerms ?? '',
                              decoration: const InputDecoration(labelText: 'Payment Terms', border: OutlineInputBorder(), hintText: 'e.g. Net 30'),
                              onChanged: (v) => extData.paymentTerms = v,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      TextFormField(
                        key: ValueKey('inv_period_${extData.invoicePeriod}'),
                        initialValue: extData.invoicePeriod ?? '',
                        decoration: const InputDecoration(labelText: 'Invoice / Billing Period', border: OutlineInputBorder(), hintText: 'e.g. 01.09.2026 - 30.09.2026', prefixIcon: Icon(Icons.calendar_today_outlined, size: 16)),
                        onChanged: (v) => extData.invoicePeriod = v,
                      ),
                      const SizedBox(height: 10),
                      Row(
                        children: [
                          Expanded(
                            child: TextFormField(
                              key: ValueKey('inv_po_${extData.poNumber}'),
                              initialValue: extData.poNumber ?? '',
                              decoration: const InputDecoration(labelText: 'PO Number / Reference', border: OutlineInputBorder()),
                              onChanged: (v) => extData.poNumber = v,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: TextFormField(
                              key: ValueKey('inv_cat_${extData.category}'),
                              initialValue: extData.category ?? '',
                              decoration: const InputDecoration(labelText: 'Service Category', border: OutlineInputBorder(), hintText: 'e.g. Support Services'),
                              onChanged: (v) => extData.category = v,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),

            // Dedicated Statutory Place of Supply (POS) & Tax Jurisdiction Bar
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: isDark ? const Color(0xFF0F172A).withValues(alpha: 0.6) : const Color(0xFFF8FAFC),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                  color: isDark ? const Color(0xFF334155) : const Color(0xFFE2E8F0),
                ),
              ),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: const Color(0xFF0284C7).withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(Icons.location_on_rounded, color: Color(0xFF0284C7), size: 18),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    flex: 3,
                    child: TextFormField(
                      key: ValueKey('pos_hdr_${extData.placeOfSupply}'),
                      initialValue: extData.placeOfSupply ?? '',
                      decoration: InputDecoration(
                        labelText: 'Place of Supply (POS) - State Code & Name',
                        hintText: 'e.g. 36 - Telangana or 27 - Maharashtra',
                        border: const OutlineInputBorder(),
                        isDense: true,
                        prefixIcon: const Icon(Icons.pin_drop_outlined, size: 16),
                        suffixIcon: (extData.placeOfSupply != null && extData.placeOfSupply!.isNotEmpty)
                            ? const Icon(Icons.check_circle, size: 16, color: Color(0xFF10B981))
                            : null,
                      ),
                      onChanged: (v) {
                        extData.placeOfSupply = v;
                        invProv.updateGst(placeOfSupply: v);
                      },
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    flex: 2,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                      decoration: BoxDecoration(
                        color: (invProv.isInterState ? Colors.purple : Colors.teal).withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: (invProv.isInterState ? Colors.purple : Colors.teal).withValues(alpha: 0.3),
                        ),
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(
                            invProv.isInterState ? Icons.swap_horiz_rounded : Icons.check_circle_outline_rounded,
                            size: 14,
                            color: invProv.isInterState ? Colors.purpleAccent : Colors.teal,
                          ),
                          const SizedBox(width: 6),
                          Flexible(
                            child: Text(
                              invProv.isInterState ? 'Inter-State (IGST)' : 'Intra-State (CGST+SGST)',
                              style: TextStyle(
                                fontSize: 11.5,
                                fontWeight: FontWeight.bold,
                                color: invProv.isInterState ? Colors.purpleAccent : Colors.teal,
                              ),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 14),
            // Notes and Internal Financial Remarks Field
            TextFormField(
              key: ValueKey('inv_notes_${extData.notes}'),
              initialValue: extData.notes ?? '',
              maxLines: 2,
              decoration: const InputDecoration(
                labelText: 'Notes, Disclaimers & Financial Remarks',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.note_alt_outlined, size: 18),
                hintText: 'Add internal audit notes or statutory references...',
              ),
              onChanged: (v) => extData.notes = v,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBankDetailsSection(BuildContext context, ExtractedInvoiceData extData) {
    final bank = extData.bankDetails ??= BankDetails();
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return GlassCard(
      key: ValueKey('bank_${bank.accountNumber}_${bank.ifscCode}_${bank.bankName}_${bank.upiId}'),
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  const Icon(Icons.account_balance_outlined, color: Color(0xFF6366F1), size: 20),
                  const SizedBox(width: 8),
                  Text(
                    'Vendor Bank Details & Payment Settlement',
                    style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.bold),
                  ),
                ],
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: isDark ? const Color(0xFF6366F1).withValues(alpha: 0.15) : const Color(0xFFEEF2FF),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0xFF6366F1).withValues(alpha: 0.3)),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      (bank.accountNumber != null && bank.accountNumber!.isNotEmpty)
                          ? Icons.check_circle_outline
                          : Icons.info_outline,
                      size: 13,
                      color: const Color(0xFF6366F1),
                    ),
                    const SizedBox(width: 4),
                    Text(
                      (bank.accountNumber != null && bank.accountNumber!.isNotEmpty)
                          ? 'Bank Extracted'
                          : 'Settlement Info',
                      style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Color(0xFF6366F1)),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  children: [
                    TextFormField(
                      key: ValueKey('bank_holder_${bank.accountHolderName}'),
                      initialValue: bank.accountHolderName ?? extData.vendorName ?? '',
                      decoration: const InputDecoration(
                        labelText: 'Beneficiary / Account Holder Name',
                        border: OutlineInputBorder(),
                        prefixIcon: Icon(Icons.person_outline, size: 16),
                      ),
                      onChanged: (v) => bank.accountHolderName = v,
                    ),
                    const SizedBox(height: 10),
                    TextFormField(
                      key: ValueKey('bank_acc_${bank.accountNumber}'),
                      initialValue: bank.accountNumber ?? '',
                      decoration: const InputDecoration(
                        labelText: 'Bank Account Number',
                        border: OutlineInputBorder(),
                        prefixIcon: Icon(Icons.numbers, size: 16),
                      ),
                      onChanged: (v) => bank.accountNumber = v,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  children: [
                    TextFormField(
                      key: ValueKey('bank_ifsc_${bank.ifscCode}'),
                      initialValue: bank.ifscCode ?? '',
                      decoration: const InputDecoration(
                        labelText: 'IFSC Code',
                        border: OutlineInputBorder(),
                        prefixIcon: Icon(Icons.pin_outlined, size: 16),
                      ),
                      onChanged: (v) => bank.ifscCode = v,
                    ),
                    const SizedBox(height: 10),
                    TextFormField(
                      key: ValueKey('bank_name_${bank.bankName}'),
                      initialValue: bank.bankName ?? '',
                      decoration: const InputDecoration(
                        labelText: 'Bank Name & Branch',
                        border: OutlineInputBorder(),
                        prefixIcon: Icon(Icons.account_balance, size: 16),
                      ),
                      onChanged: (v) => bank.bankName = v,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  children: [
                    TextFormField(
                      key: ValueKey('bank_upi_${bank.upiId}'),
                      initialValue: bank.upiId ?? '',
                      decoration: const InputDecoration(
                        labelText: 'UPI ID / VPA',
                        border: OutlineInputBorder(),
                        prefixIcon: Icon(Icons.qr_code_2, size: 16),
                      ),
                      onChanged: (v) => bank.upiId = v,
                    ),
                    const SizedBox(height: 10),
                    TextFormField(
                      key: ValueKey('bank_branch_${bank.branch}'),
                      initialValue: bank.branch ?? '',
                      decoration: const InputDecoration(
                        labelText: 'Branch Location',
                        border: OutlineInputBorder(),
                        prefixIcon: Icon(Icons.location_on_outlined, size: 16),
                      ),
                      onChanged: (v) => bank.branch = v,
                    ),
                  ],
                ),
              ),
            ],
          ),
          if (bank.rawText != null && bank.rawText!.trim().isNotEmpty) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: isDark ? Colors.black26 : Colors.grey.shade100,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: isDark ? Colors.white12 : Colors.black12),
              ),
              child: Row(
                children: [
                  const Icon(Icons.receipt_outlined, size: 14, color: Colors.grey),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      'Raw Extracted Bank Text: "${bank.rawText}"',
                      style: const TextStyle(fontSize: 11, fontStyle: FontStyle.italic, color: Colors.grey),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildZohoExportAuditCard(BuildContext context, Invoice invoice, InvoiceProvider invProv) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final isExported = invoice.displayStatus == 'exported' || (invoice.zohoBillId != null && invoice.zohoBillId!.isNotEmpty);
    final zohoBillId = invoice.zohoBillId ?? 'Not generated';
    final zohoBillNum = invoice.zohoBillNumber ?? invoice.extractedData?.invoiceNumber ?? 'Pending';
    final timestamp = invoice.updatedAt ?? invoice.createdAt;
    final exportedAt = timestamp != null ? DateFormat('dd MMM yyyy, hh:mm a').format(timestamp) : 'Not exported yet';

    return GlassCard(
      borderRadius: 16,
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: (isExported ? const Color(0xFF10B981) : const Color(0xFF6366F1)).withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Icon(
                        isExported ? Icons.cloud_done_rounded : Icons.cloud_upload_outlined,
                        color: isExported ? const Color(0xFF10B981) : const Color(0xFF6366F1),
                        size: 20,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Text(
                                'Zoho Books Integration & Audit',
                                style: TextStyle(
                                  fontSize: 15,
                                  fontWeight: FontWeight.w700,
                                  color: isDark ? Colors.white : const Color(0xFF0F172A),
                                ),
                              ),
                              const SizedBox(width: 8),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                                decoration: BoxDecoration(
                                  color: (isExported ? const Color(0xFF10B981) : const Color(0xFFF59E0B)).withValues(alpha: 0.15),
                                  borderRadius: BorderRadius.circular(6),
                                ),
                                child: Text(
                                  isExported ? 'SYNCED' : 'PENDING SYNC',
                                  style: TextStyle(
                                    fontSize: 9.5,
                                    fontWeight: FontWeight.bold,
                                    color: isExported ? const Color(0xFF10B981) : const Color(0xFFF59E0B),
                                    letterSpacing: 0.5,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 2),
                          Text(
                            isExported
                                ? 'Bill ledger record posted with line-level COA, TDS withholding & original PDF attachment'
                                : 'Review statutory taxes & line-item accounts before exporting to Zoho Books',
                            style: TextStyle(
                              fontSize: 11.5,
                              color: isDark ? AppTheme.darkTextMuted : AppTheme.lightTextMuted,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              if (!isExported)
                ElevatedButton.icon(
                  onPressed: invProv.isExporting ? null : () => invProv.exportToZoho(),
                  icon: invProv.isExporting
                      ? const SizedBox(width: 12, height: 12, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                      : const Icon(Icons.send_rounded, size: 14),
                  label: const Text('Export to Zoho'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF6366F1),
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                    textStyle: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
                  ),
                )
              else
                OutlinedButton.icon(
                  onPressed: invProv.isExporting
                      ? null
                      : () async {
                          final ok = await invProv.exportToZoho();
                          if (context.mounted && ok) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(
                                content: Text('Invoice successfully resynced and updated in Zoho Books!'),
                                backgroundColor: Color(0xFF10B981),
                              ),
                            );
                          }
                        },
                  icon: const Icon(Icons.sync_rounded, size: 14),
                  label: const Text('Resync Bill'),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    textStyle: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600),
                  ),
                ),
            ],
          ),
          if (isExported) ...[
            const SizedBox(height: 14),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: isDark ? const Color(0xFF131D33) : const Color(0xFFF8FAFC),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                  color: isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0),
                ),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Zoho Bill ID', style: TextStyle(fontSize: 10.5, color: isDark ? AppTheme.darkTextMuted : AppTheme.lightTextMuted)),
                        const SizedBox(height: 2),
                        SelectableText(
                          zohoBillId,
                          style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                  ),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Bill Number', style: TextStyle(fontSize: 10.5, color: isDark ? AppTheme.darkTextMuted : AppTheme.lightTextMuted)),
                        const SizedBox(height: 2),
                        SelectableText(
                          zohoBillNum,
                          style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                  ),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Exported At', style: TextStyle(fontSize: 10.5, color: isDark ? AppTheme.darkTextMuted : AppTheme.lightTextMuted)),
                        const SizedBox(height: 2),
                        Text(
                          exportedAt,
                          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                        ),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: const Color(0xFF10B981).withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.attach_file_rounded, size: 12, color: Color(0xFF10B981)),
                        SizedBox(width: 4),
                        Text(
                          'PDF Attached',
                          style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.bold, color: Color(0xFF10B981)),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

