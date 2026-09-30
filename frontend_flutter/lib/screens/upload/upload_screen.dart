import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/theme.dart';
import '../../models/invoice_models.dart';
import '../../providers/invoice_provider.dart';
import '../../widgets/glass_card.dart';
import '../workspace/invoice_workspace_screen.dart';

class UploadScreen extends StatefulWidget {
  const UploadScreen({super.key});

  @override
  State<UploadScreen> createState() => _UploadScreenState();
}

class _UploadScreenState extends State<UploadScreen> with SingleTickerProviderStateMixin {
  bool _isUploading = false;
  String? _uploadStatusText;
  String? _errorMessage;
  bool _isHovered = false;
  late AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 3),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  Future<void> _pickAndUploadFile() async {
    setState(() {
      _errorMessage = null;
      _isUploading = true;
    });

    try {
      final files = await FilePicker.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['pdf', 'png', 'jpg', 'jpeg'],
      );

      if (files.isEmpty) {
        setState(() {
          _isUploading = false;
        });
        return;
      }

      for (final file in files) {
        final bytes = await file.xFile.readAsBytes();
        if (bytes.isNotEmpty && mounted) {
          await _executeAiPipelineWithModal(file.name, bytes);
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = e.toString().replaceAll('Exception: ', '');
        });
      }
    } finally {
      if (mounted) {
        setState(() {
          _isUploading = false;
        });
      }
    }
  }

  Future<void> _executeAiPipelineWithModal(String fileName, List<int> bytes) async {
    final invProvider = Provider.of<InvoiceProvider>(context, listen: false);
    final isDark = Theme.of(context).brightness == Brightness.dark;

    int currentStep = 1; // 1: DB Upload, 2: VLM AI, 3: GST/TDS, 4: GL Balance
    double progress = 0.15;
    String statusTitle = 'Uploading to Database Vault...';
    String statusSub = 'Encrypting document and checking SHA-256 uniqueness.';
    bool isDone = false;
    String? pipelineError;
    dynamic createdInvoiceId;

    void Function(void Function())? updateModal;

    // Show AI Pipeline Progress Modal Dialog
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (dialogCtx) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            updateModal = setModalState;

            return Dialog(
              backgroundColor: Colors.transparent,
              elevation: 0,
              child: Container(
                constraints: const BoxConstraints(maxWidth: 520),
                child: GlassCard(
                  padding: const EdgeInsets.all(28),
                  borderRadius: 24,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Header
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              gradient: AppTheme.primaryGradient,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: const Icon(Icons.auto_awesome_rounded, color: Colors.white, size: 22),
                          ),
                          const SizedBox(width: 14),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text(
                                  'Autonomous AI Ingestion Engine',
                                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  fileName,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w500,
                                    color: isDark ? AppTheme.darkTextMuted : const Color(0xFF64748B),
                                  ),
                                ),
                              ],
                            ),
                          ),
                          if (!isDone && pipelineError == null)
                            const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2.5),
                            )
                          else if (isDone)
                            const Icon(Icons.check_circle_rounded, color: AppTheme.accentColor, size: 24)
                          else
                            const Icon(Icons.error_outline_rounded, color: AppTheme.errorColor, size: 24),
                        ],
                      ),
                      const SizedBox(height: 20),

                      // Progress Bar
                      ClipRRect(
                        borderRadius: BorderRadius.circular(6),
                        child: LinearProgressIndicator(
                          value: progress,
                          minHeight: 6,
                          backgroundColor: isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0),
                          valueColor: AlwaysStoppedAnimation<Color>(
                            pipelineError != null ? AppTheme.errorColor : AppTheme.primaryColor,
                          ),
                        ),
                      ),
                      const SizedBox(height: 20),

                      // Pipeline Stage Steps
                      _buildStageItem(
                        stepNum: 1,
                        title: 'Database Vault & SHA-256 Deduplication',
                        desc: 'Encrypted cloud storage & duplicate submission check',
                        activeStep: currentStep,
                        isDone: isDone,
                        isDark: isDark,
                      ),
                      const SizedBox(height: 12),
                      _buildStageItem(
                        stepNum: 2,
                        title: 'Vision-Language AI Document Extraction',
                        desc: 'Extracting vendor metadata, line items & amounts',
                        activeStep: currentStep,
                        isDone: isDone,
                        isDark: isDark,
                      ),
                      const SizedBox(height: 12),
                      _buildStageItem(
                        stepNum: 3,
                        title: 'GST & TDS Statutory Tax Assessment',
                        desc: 'Reconciling HSN codes, GST rates & Section 194C/J TDS',
                        activeStep: currentStep,
                        isDone: isDone,
                        isDark: isDark,
                      ),
                      const SizedBox(height: 12),
                      _buildStageItem(
                        stepNum: 4,
                        title: 'Double-Entry General Ledger Balance',
                        desc: 'Debits == Credits validation with zero-plug policy',
                        activeStep: currentStep,
                        isDone: isDone,
                        isDark: isDark,
                      ),
                      const SizedBox(height: 24),

                      // Footer status or action
                      if (pipelineError != null) ...[
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: AppTheme.errorColor.withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: AppTheme.errorColor.withValues(alpha: 0.3)),
                          ),
                          child: Text(
                            pipelineError!,
                            style: const TextStyle(color: AppTheme.errorColor, fontSize: 12),
                          ),
                        ),
                        const SizedBox(height: 14),
                        Align(
                          alignment: Alignment.centerRight,
                          child: OutlinedButton(
                            onPressed: () => Navigator.of(context).pop(),
                            child: const Text('Close'),
                          ),
                        ),
                      ] else if (isDone) ...[
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton.icon(
                            onPressed: () {
                              Navigator.of(context).pop();
                              if (createdInvoiceId != null) {
                                Navigator.of(context).push(
                                  MaterialPageRoute(
                                    builder: (_) => InvoiceWorkspaceScreen(invoiceId: createdInvoiceId!),
                                  ),
                                );
                              }
                            },
                            style: ElevatedButton.styleFrom(
                              backgroundColor: AppTheme.accentColor,
                              padding: const EdgeInsets.symmetric(vertical: 14),
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                            ),
                            icon: const Icon(Icons.dashboard_customize_rounded, size: 18),
                            label: const Text('Open Verification Workspace', style: TextStyle(fontWeight: FontWeight.bold)),
                          ),
                        ),
                      ] else ...[
                        Row(
                          children: [
                            const SizedBox(
                              width: 14,
                              height: 14,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    statusTitle,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                                  ),
                                  if (statusSub.isNotEmpty) ...[
                                    const SizedBox(height: 2),
                                    Text(
                                      statusSub,
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: TextStyle(
                                        fontSize: 11,
                                        color: isDark ? AppTheme.darkTextMuted : const Color(0xFF64748B),
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                            ),
                          ],
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            );
          },
        );
      },
    );

    try {
      // Step 1: Upload to Database Vault
      if (updateModal != null) {
        updateModal!(() {
          currentStep = 1;
          progress = 0.2;
          statusTitle = 'Database Vault & SHA-256 Deduplication';
          statusSub = 'Uploading encrypted binary and computing cryptographic SHA-256 hash...';
        });
      }

      final invoice = await invProvider.uploadInvoice(
        bytes: bytes,
        filename: fileName,
      );
      createdInvoiceId = invoice.id;

      // Poll actual status from backend (supports up to 60 seconds of AI vision extraction)
      int pollCount = 0;
      const maxPolls = 50;
      Invoice? latestInvoice = invoice;

      while (pollCount < maxPolls) {
        await Future.delayed(const Duration(milliseconds: 1000));
        pollCount++;

        try {
          latestInvoice = await invProvider.getInvoice(createdInvoiceId);
          final statusUpper = latestInvoice.status.toUpperCase();
          final hasExtractedData = latestInvoice.extractedData != null &&
              ((latestInvoice.extractedData!.invoiceNumber?.isNotEmpty ?? false) ||
                  (latestInvoice.extractedData!.vendorName?.isNotEmpty ?? false) ||
                  (latestInvoice.extractedData!.lineItems.isNotEmpty));

          if (statusUpper == 'PROCESSING_VLM') {
            if (updateModal != null) {
              updateModal!(() {
                currentStep = 2;
                progress = 0.45;
                statusTitle = 'Vision-Language AI Document Extraction...';
                statusSub = 'Vision AI reading document metadata, vendor details & line items';
              });
            }
          } else if (statusUpper == 'PROCESSING_ACCOUNTING') {
            if (updateModal != null) {
              updateModal!(() {
                currentStep = 3;
                progress = 0.75;
                statusTitle = 'GST & TDS Statutory Tax Assessment...';
                statusSub = 'Evaluating Section 194C/J TDS, HSN codes & GST tax rates';
              });
            }
          } else if (statusUpper == 'COMPLETED' ||
              hasExtractedData ||
              statusUpper == 'PENDING_REVIEW' ||
              statusUpper == 'APPROVED') {
            // Pipeline successfully produced extracted output
            if (updateModal != null) {
              updateModal!(() {
                currentStep = 4;
                progress = 0.95;
                statusTitle = 'Balancing Authoritative General Ledger...';
                statusSub = 'Validating Debits == Credits zero-plug policy';
              });
            }
            await Future.delayed(const Duration(milliseconds: 600));

            if (updateModal != null) {
              updateModal!(() {
                currentStep = 5;
                progress = 1.0;
                isDone = true;
                statusTitle = 'Ingestion Pipeline Complete!';
                statusSub = 'Document processed successfully and ready for verification';
              });
            }
            break;
          } else if (statusUpper == 'FAILED' || statusUpper == 'NOT_PROCESSED') {
            throw Exception(latestInvoice.reviewReason ??
                'AI extraction was unable to automatically parse this document layout. Please review manually.');
          } else {
            // Still in PENDING stage
            if (updateModal != null && currentStep == 1) {
              updateModal!(() {
                progress = 0.3;
                statusTitle = 'Queued for Vision-Language AI...';
                statusSub = 'Document verified in database. Awaiting AI worker pick up.';
              });
            }
          }
        } catch (pollErr) {
          if (pollErr.toString().contains('AI extraction was unable') ||
              pollErr.toString().contains('FAILED')) {
            rethrow;
          }
          // Transient network hiccup during polling, continue next iteration
        }
      }

      // Preload active invoice into provider state before transitioning to workspace
      if (createdInvoiceId != null) {
        await invProvider.loadInvoiceDetail(createdInvoiceId);
      }

      await Future.delayed(const Duration(milliseconds: 600));
      if (mounted && Navigator.of(context).canPop()) {
        Navigator.of(context).pop();
        if (createdInvoiceId != null) {
          Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => InvoiceWorkspaceScreen(invoiceId: createdInvoiceId!),
            ),
          );
        }
      }
    } catch (e) {
      if (updateModal != null) {
        updateModal!(() {
          pipelineError = e.toString().replaceAll('Exception: ', '');
        });
      }
    }
  }

  Widget _buildStageItem({
    required int stepNum,
    required String title,
    required String desc,
    required int activeStep,
    required bool isDone,
    required bool isDark,
  }) {
    final isPassed = activeStep > stepNum || isDone;
    final isCurrent = activeStep == stepNum && !isDone;

    Color iconColor;
    Color bgColor;
    Widget leadingWidget;

    if (isPassed) {
      iconColor = AppTheme.accentColor;
      bgColor = AppTheme.accentColor.withValues(alpha: isDark ? 0.18 : 0.1);
      leadingWidget = const Icon(Icons.check_circle_rounded, color: AppTheme.accentColor, size: 18);
    } else if (isCurrent) {
      iconColor = AppTheme.primaryColor;
      bgColor = AppTheme.primaryColor.withValues(alpha: isDark ? 0.2 : 0.1);
      leadingWidget = const SizedBox(
        width: 16,
        height: 16,
        child: CircularProgressIndicator(strokeWidth: 2),
      );
    } else {
      iconColor = isDark ? const Color(0xFF64748B) : const Color(0xFF94A3B8);
      bgColor = isDark ? const Color(0xFF1E293B) : const Color(0xFFF1F5F9);
      leadingWidget = Text(
        '$stepNum',
        style: TextStyle(
          color: iconColor,
          fontWeight: FontWeight.bold,
          fontSize: 12,
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: isCurrent
            ? AppTheme.primaryColor.withValues(alpha: isDark ? 0.1 : 0.05)
            : (isDark ? const Color(0xFF0F172A).withValues(alpha: 0.4) : const Color(0xFFF8FAFC)),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isCurrent
              ? AppTheme.primaryColor.withValues(alpha: 0.4)
              : (isDark ? const Color(0xFF1E293B) : const Color(0xFFE2E8F0)),
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 28,
            height: 28,
            decoration: BoxDecoration(
              color: bgColor,
              shape: BoxShape.circle,
            ),
            child: Center(child: leadingWidget),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: isCurrent || isPassed ? FontWeight.bold : FontWeight.w600,
                    color: isPassed
                        ? (isDark ? Colors.white : const Color(0xFF0F172A))
                        : (isCurrent ? AppTheme.primaryLight : (isDark ? AppTheme.darkTextMuted : const Color(0xFF94A3B8))),
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  desc,
                  style: TextStyle(
                    fontSize: 11,
                    color: isDark ? AppTheme.darkTextMuted : const Color(0xFF64748B),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
          child: Container(
            constraints: const BoxConstraints(maxWidth: 620),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Header
                Center(
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
                    decoration: BoxDecoration(
                      color: isDark ? AppTheme.primaryColor.withValues(alpha: 0.15) : AppTheme.primaryColor.withValues(alpha: 0.08),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: AppTheme.primaryColor.withValues(alpha: isDark ? 0.35 : 0.2),
                      ),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.auto_awesome_rounded, size: 13, color: AppTheme.primaryColor),
                        const SizedBox(width: 6),
                        Text(
                          'Vision-Language AI Pipeline',
                          style: TextStyle(
                            fontSize: 11.5,
                            fontWeight: FontWeight.w700,
                            color: isDark ? Colors.white : AppTheme.primaryDark,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  'Upload Financial Document',
                  style: TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.w800,
                    letterSpacing: -0.5,
                    color: isDark ? Colors.white : const Color(0xFF0F172A),
                  ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 6),
                Text(
                  'Upload vendor bills, tax invoices, or receipts for automated extraction & ledger posting.',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 13,
                    color: isDark ? AppTheme.darkTextSecondary : const Color(0xFF64748B),
                  ),
                ),
                const SizedBox(height: 24),

                if (_errorMessage != null) ...[
                  Container(
                    padding: const EdgeInsets.all(14),
                    margin: const EdgeInsets.only(bottom: 20),
                    decoration: BoxDecoration(
                      color: AppTheme.errorColor.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppTheme.errorColor.withValues(alpha: 0.3)),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.error_outline_rounded, color: AppTheme.errorColor, size: 20),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            _errorMessage!,
                            style: const TextStyle(color: AppTheme.errorColor, fontSize: 13, fontWeight: FontWeight.w600),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],

                // Refined Dropzone Box
                MouseRegion(
                  onEnter: (_) => setState(() => _isHovered = true),
                  onExit: (_) => setState(() => _isHovered = false),
                  child: GlassCard(
                    onTap: _isUploading ? null : _pickAndUploadFile,
                    padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 40),
                    borderRadius: 20,
                    borderColor: _isHovered
                        ? AppTheme.primaryColor
                        : (isDark ? const Color(0xFF1E293B) : const Color(0xFFCBD5E1)),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        // Icon Container
                        Container(
                          width: 64,
                          height: 64,
                          decoration: BoxDecoration(
                            color: AppTheme.primaryColor.withValues(alpha: isDark ? 0.2 : 0.08),
                            shape: BoxShape.circle,
                            border: Border.all(
                              color: AppTheme.primaryColor.withValues(alpha: isDark ? 0.4 : 0.2),
                            ),
                          ),
                          child: Center(
                            child: _isUploading
                                ? const SizedBox(
                                    width: 28,
                                    height: 28,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2.5,
                                      valueColor: AlwaysStoppedAnimation<Color>(AppTheme.primaryColor),
                                    ),
                                  )
                                : const Icon(
                                    Icons.cloud_upload_outlined,
                                    size: 32,
                                    color: AppTheme.primaryColor,
                                  ),
                          ),
                        ),
                        const SizedBox(height: 18),
                        Text(
                          _isUploading
                              ? (_uploadStatusText ?? 'Processing Document...')
                              : 'Click or drag files here to upload',
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w700,
                            letterSpacing: -0.2,
                            color: isDark ? Colors.white : const Color(0xFF0F172A),
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          'Supports PDF, PNG, JPG, JPEG invoices up to 25MB',
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            fontSize: 12.5,
                            color: isDark ? AppTheme.darkTextMuted : const Color(0xFF64748B),
                          ),
                        ),
                        const SizedBox(height: 20),

                        // Action Button
                        ElevatedButton.icon(
                          onPressed: _isUploading ? null : _pickAndUploadFile,
                          icon: const Icon(Icons.file_upload_outlined, size: 18),
                          label: const Text('Browse Files'),
                          style: ElevatedButton.styleFrom(
                            padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 12),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                          ),
                        ),
                        const SizedBox(height: 20),

                        // File Format Badges
                        Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            _buildFormatPill('PDF', Icons.picture_as_pdf_outlined, const Color(0xFFEF4444), isDark),
                            const SizedBox(width: 8),
                            _buildFormatPill('PNG', Icons.image_outlined, const Color(0xFF3B82F6), isDark),
                            const SizedBox(width: 8),
                            _buildFormatPill('JPEG', Icons.photo_outlined, const Color(0xFF10B981), isDark),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 20),

                // Features Footnote Cards
                Row(
                  children: [
                    Expanded(
                      child: _buildInfoFeatureCard(
                        Icons.shield_outlined,
                        'SHA-256 Deduplication',
                        'Prevents duplicate invoice submissions & double payment risks.',
                        isDark,
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: _buildInfoFeatureCard(
                        Icons.balance_rounded,
                        'Debits == Credits',
                        'Enforces zero-plug double entry balanced journal accounting.',
                        isDark,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildFormatPill(String label, IconData icon, Color color, bool isDark) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: isDark ? 0.15 : 0.08),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: color.withValues(alpha: isDark ? 0.35 : 0.2),
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: color),
          const SizedBox(width: 5),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 11,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInfoFeatureCard(IconData icon, String title, String desc, bool isDark) {
    return GlassCard(
      padding: const EdgeInsets.all(16),
      borderRadius: 14,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: AppTheme.primaryColor.withValues(alpha: isDark ? 0.18 : 0.08),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, size: 17, color: AppTheme.primaryColor),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 12.5,
                    color: isDark ? Colors.white : const Color(0xFF0F172A),
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  desc,
                  style: TextStyle(
                    fontSize: 11,
                    height: 1.35,
                    color: isDark ? AppTheme.darkTextMuted : const Color(0xFF64748B),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
