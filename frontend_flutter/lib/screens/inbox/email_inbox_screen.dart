import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../config/theme.dart';
import '../../models/integration_models.dart';
import '../../providers/integration_provider.dart';
import '../../widgets/glass_card.dart';
import '../../widgets/pdf_frame.dart';
import '../../widgets/skeleton_loader.dart';
import '../workspace/invoice_workspace_screen.dart';

class EmailInboxScreen extends StatefulWidget {
  const EmailInboxScreen({super.key});

  @override
  State<EmailInboxScreen> createState() => _EmailInboxScreenState();
}

class _EmailInboxScreenState extends State<EmailInboxScreen> {
  final Map<String, bool> _loadingPdfMap = {};
  final Map<String, bool> _processingMap = {};
  final TextEditingController _searchController = TextEditingController();
  String _selectedOrigin = 'all'; // 'all', 'indian', 'foreign'
  String _searchQuery = '';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<IntegrationProvider>(context, listen: false).fetchStatus();
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  void _showNotification(String message, {bool isError = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: isError ? AppTheme.errorColor : AppTheme.accentColor,
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 4),
      ),
    );
  }

  String _formatFileSize(int bytes) {
    if (bytes <= 0) return '0 B';
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${(bytes / (1024 * 1024)).toStringAsFixed(2)} MB';
  }

  Future<void> _openPdf(EmailMessage msg) async {
    setState(() => _loadingPdfMap[msg.id] = true);
    try {
      final intProvider = Provider.of<IntegrationProvider>(context, listen: false);
      final rawBytes = await intProvider.getInvoiceFileBytes(msg.id);
      final bytes = Uint8List.fromList(rawBytes);

      if (kIsWeb) {
        // Web handling: use Blob URL via web interop to avoid browser data URL navigation blocks
        openBlobInNewTab(bytes, msg.mimeType ?? 'application/pdf');
        _showNotification('Document opened in new tab.');
      } else {
        // Desktop / Native handling
        final tempDir = Directory.systemTemp.createTempSync('sakshi_doc_');
        final rawName = msg.fileName ?? 'invoice_${msg.id.substring(0, 8)}.pdf';
        final cleanName = rawName.replaceAll(RegExp(r'[^\w\.-]'), '_');
        final filePath = '${tempDir.path}/$cleanName';
        final file = File(filePath);
        await file.writeAsBytes(bytes);

        if (Platform.isLinux) {
          await Process.run('xdg-open', [file.path]);
        } else if (Platform.isMacOS) {
          await Process.run('open', [file.path]);
        } else if (Platform.isWindows) {
          await Process.run('cmd', ['/c', 'start', '', file.path]);
        } else {
          final uri = Uri.file(file.path);
          if (await canLaunchUrl(uri)) {
            await launchUrl(uri);
          }
        }
        _showNotification('Opened ${msg.fileName ?? "document"} in system viewer.');
      }
    } catch (e) {
      _showNotification('Failed to preview document: ${e.toString().replaceAll("Exception: ", "")}', isError: true);
    } finally {
      if (mounted) {
        setState(() => _loadingPdfMap[msg.id] = false);
      }
    }
  }

  void _showDocumentPreviewModal(EmailMessage msg) {
    final isPdf = (msg.mimeType?.contains('pdf') ?? false) || (msg.fileName?.toLowerCase().endsWith('.pdf') ?? false);
    final isDark = Theme.of(context).brightness == Brightness.dark;

    showDialog(
      context: context,
      builder: (ctx) {
        return Dialog(
          backgroundColor: isDark ? const Color(0xFF0F172A) : Colors.white,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          insetPadding: const EdgeInsets.symmetric(horizontal: 24, vertical: 24),
          child: Container(
            width: 1050,
            height: 820,
            constraints: BoxConstraints(
              maxWidth: MediaQuery.of(ctx).size.width * 0.95,
              maxHeight: MediaQuery.of(ctx).size.height * 0.92,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Modal Header
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
                  decoration: BoxDecoration(
                    color: isDark ? const Color(0xFF1E293B) : const Color(0xFFF8FAFC),
                    borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
                    border: Border(
                      bottom: BorderSide(
                        color: isDark ? const Color(0xFF334155) : const Color(0xFFE2E8F0),
                      ),
                    ),
                  ),
                  child: Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: (isPdf ? const Color(0xFFEF4444) : AppTheme.primaryColor).withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Icon(
                          isPdf ? Icons.picture_as_pdf_rounded : Icons.image_rounded,
                          color: isPdf ? const Color(0xFFEF4444) : AppTheme.primaryColor,
                          size: 20,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              msg.fileName ?? msg.subject,
                              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                              overflow: TextOverflow.ellipsis,
                            ),
                            const SizedBox(height: 2),
                            Text(
                              'From: ${msg.sender} • ${_formatFileSize(msg.fileSize)}',
                              style: TextStyle(
                                fontSize: 12,
                                color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 12),
                      OutlinedButton.icon(
                        onPressed: () => _openPdf(msg),
                        icon: const Icon(Icons.open_in_new_rounded, size: 15),
                        label: const Text('Open in New Tab', style: TextStyle(fontSize: 12)),
                        style: OutlinedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                        ),
                      ),
                      const SizedBox(width: 8),
                      ElevatedButton.icon(
                        onPressed: () {
                          Navigator.of(ctx).pop();
                          _processAndNavigate(msg);
                        },
                        icon: const Icon(Icons.play_arrow_rounded, size: 16),
                        label: const Text('Process to Workspace', style: TextStyle(fontSize: 12)),
                        style: ElevatedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                        ),
                      ),
                      const SizedBox(width: 8),
                      IconButton(
                        onPressed: () => Navigator.of(ctx).pop(),
                        icon: const Icon(Icons.close_rounded, size: 20),
                        tooltip: 'Close',
                      ),
                    ],
                  ),
                ),

                // Modal Content / Document Preview
                Expanded(
                  child: FutureBuilder<Uint8List>(
                    future: Provider.of<IntegrationProvider>(context, listen: false)
                        .getInvoiceFileBytes(msg.id)
                        .then((b) => Uint8List.fromList(b)),
                    builder: (context, snapshot) {
                      if (snapshot.connectionState == ConnectionState.waiting) {
                        return const DocumentPreviewSkeleton();
                      }

                      if (snapshot.hasError || !snapshot.hasData || snapshot.data!.isEmpty) {
                        return Center(
                          child: Padding(
                            padding: const EdgeInsets.all(24),
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const Icon(Icons.error_outline_rounded, size: 48, color: AppTheme.errorColor),
                                const SizedBox(height: 12),
                                const Text(
                                  'Failed to load document preview',
                                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                                ),
                                const SizedBox(height: 6),
                                Text(
                                  '${snapshot.error ?? "No document data returned."}',
                                  style: const TextStyle(fontSize: 12, color: Color(0xFF94A3B8)),
                                  textAlign: TextAlign.center,
                                ),
                                const SizedBox(height: 16),
                                ElevatedButton.icon(
                                  onPressed: () => _openPdf(msg),
                                  icon: const Icon(Icons.launch_rounded, size: 16),
                                  label: const Text('Try Opening Directly'),
                                ),
                              ],
                            ),
                          ),
                        );
                      }

                      final bytes = snapshot.data!;

                      if (isPdf) {
                        if (kIsWeb) {
                          return ClipRRect(
                            borderRadius: const BorderRadius.vertical(bottom: Radius.circular(16)),
                            child: buildPdfFrame(
                              url: '',
                              viewId: msg.id,
                              bytes: bytes,
                            ),
                          );
                        } else {
                          return Center(
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const Icon(Icons.picture_as_pdf_rounded, size: 64, color: Color(0xFFEF4444)),
                                const SizedBox(height: 16),
                                Text(
                                  msg.fileName ?? 'Invoice Document',
                                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                                ),
                                const SizedBox(height: 6),
                                Text(
                                  'Size: ${_formatFileSize(bytes.length)}',
                                  style: const TextStyle(fontSize: 13, color: Color(0xFF94A3B8)),
                                ),
                                const SizedBox(height: 20),
                                ElevatedButton.icon(
                                  onPressed: () => _openPdf(msg),
                                  icon: const Icon(Icons.open_in_new_rounded, size: 16),
                                  label: const Text('Open in System Viewer'),
                                ),
                              ],
                            ),
                          );
                        }
                      } else {
                        // Image file
                        return Container(
                          color: isDark ? const Color(0xFF020617) : const Color(0xFF0F172A),
                          child: InteractiveViewer(
                            panEnabled: true,
                            boundaryMargin: const EdgeInsets.all(20),
                            minScale: 0.5,
                            maxScale: 4.0,
                            child: Center(
                              child: Image.memory(
                                bytes,
                                fit: BoxFit.contain,
                                errorBuilder: (context, error, stackTrace) => const Center(
                                  child: Text('Unable to render image.', style: TextStyle(color: Colors.white)),
                                ),
                              ),
                            ),
                          ),
                        );
                      }
                    },
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Future<void> _processAndNavigate(EmailMessage msg) async {
    setState(() => _processingMap[msg.id] = true);
    try {
      final intProvider = Provider.of<IntegrationProvider>(context, listen: false);
      await intProvider.processStagedDocument(msg.id);
      _showNotification('Invoice queued for processing. Opening workspace...');

      if (mounted) {
        Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => InvoiceWorkspaceScreen(invoiceId: msg.id),
          ),
        );
      }
    } catch (e) {
      _showNotification('Failed to process invoice: ${e.toString().replaceAll("Exception: ", "")}', isError: true);
    } finally {
      if (mounted) {
        setState(() => _processingMap[msg.id] = false);
      }
    }
  }

  Future<void> _confirmDelete(EmailMessage msg) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Staged Document'),
        content: Text('Are you sure you want to delete "${msg.fileName ?? msg.subject}" from inbox?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.errorColor),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Delete', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );

    if (confirm == true && mounted) {
      try {
        final intProvider = Provider.of<IntegrationProvider>(context, listen: false);
        await intProvider.deleteStagedDocument(msg.id);
        _showNotification('Staged document removed.');
      } catch (e) {
        _showNotification('Failed to delete: ${e.toString().replaceAll("Exception: ", "")}', isError: true);
      }
    }
  }

  void _showDocumentDetailsModal(EmailMessage msg) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final dateStr = msg.date != null ? DateFormat('dd MMM yyyy, hh:mm a').format(msg.date!) : 'N/A';
    final isPdf = (msg.fileName?.toLowerCase().endsWith('.pdf') ?? true) || (msg.mimeType?.contains('pdf') ?? true);

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDialogState) {
          final isProcessing = _processingMap[msg.id] == true;

          return Dialog(
            backgroundColor: isDark ? const Color(0xFF0F172A) : Colors.white,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 600),
              child: Padding(
                padding: const EdgeInsets.all(24),
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
                            color: isPdf ? const Color(0xFFEF4444).withValues(alpha: 0.15) : AppTheme.primaryColor.withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Icon(
                            isPdf ? Icons.picture_as_pdf_rounded : Icons.image_rounded,
                            color: isPdf ? const Color(0xFFEF4444) : AppTheme.primaryColor,
                            size: 26,
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                msg.fileName ?? 'Invoice Document',
                                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                                overflow: TextOverflow.ellipsis,
                              ),
                              const SizedBox(height: 2),
                              Text(
                                '${isPdf ? "PDF Document" : "Image File"} • ${_formatFileSize(msg.fileSize)}',
                                style: TextStyle(fontSize: 12, color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
                              ),
                            ],
                          ),
                        ),
                        IconButton(
                          icon: const Icon(Icons.close_rounded),
                          onPressed: () => Navigator.of(ctx).pop(),
                        ),
                      ],
                    ),
                    const Divider(height: 28),

                    // AI Classification Card
                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: isDark ? const Color(0xFF1E293B) : const Color(0xFFF8FAFC),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: isDark ? const Color(0xFF334155) : const Color(0xFFE2E8F0),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              const Icon(Icons.auto_awesome_rounded, size: 16, color: AppTheme.accentColor),
                              const SizedBox(width: 6),
                              const Text('AI Classification & Analysis', style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold)),
                              const Spacer(),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                decoration: BoxDecoration(
                                  color: AppTheme.accentColor.withValues(alpha: 0.15),
                                  borderRadius: BorderRadius.circular(6),
                                ),
                                child: Text(
                                  msg.documentType ?? 'INVOICE',
                                  style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: AppTheme.accentColor),
                                ),
                              ),
                              const SizedBox(width: 6),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                decoration: BoxDecoration(
                                  color: (msg.isForeign ? const Color(0xFF6366F1) : const Color(0xFF10B981)).withValues(alpha: 0.15),
                                  borderRadius: BorderRadius.circular(6),
                                  border: Border.all(
                                    color: (msg.isForeign ? const Color(0xFF6366F1) : const Color(0xFF10B981)).withValues(alpha: 0.35),
                                  ),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Icon(
                                      msg.isForeign ? Icons.public_rounded : Icons.flag_rounded,
                                      size: 12,
                                      color: msg.isForeign ? const Color(0xFF818CF8) : const Color(0xFF10B981),
                                    ),
                                    const SizedBox(width: 4),
                                    Text(
                                      msg.isForeign ? 'Foreign (${msg.currency ?? "USD"})' : 'Indian (INR)',
                                      style: TextStyle(
                                        fontSize: 11,
                                        fontWeight: FontWeight.bold,
                                        color: msg.isForeign ? const Color(0xFF818CF8) : const Color(0xFF10B981),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 10),
                          if (msg.classificationConfidence != null) ...[
                            Row(
                              children: [
                                Text('Confidence:', style: TextStyle(fontSize: 12, color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B))),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: ClipRRect(
                                    borderRadius: BorderRadius.circular(4),
                                    child: LinearProgressIndicator(
                                      value: msg.classificationConfidence!,
                                      backgroundColor: isDark ? const Color(0xFF334155) : const Color(0xFFCBD5E1),
                                      valueColor: const AlwaysStoppedAnimation<Color>(AppTheme.accentColor),
                                      minHeight: 6,
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Text(
                                  '${(msg.classificationConfidence! * 100).toInt()}%',
                                  style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                          ],
                          if (msg.classificationReason != null && msg.classificationReason!.isNotEmpty) ...[
                            Text(
                              'Reasoning: ${msg.classificationReason}',
                              style: TextStyle(
                                fontSize: 12,
                                height: 1.4,
                                color: isDark ? const Color(0xFFCBD5E1) : const Color(0xFF334155),
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),

                    const SizedBox(height: 16),

                    // Email Source Information
                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: isDark ? const Color(0xFF1E293B) : const Color(0xFFF8FAFC),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: isDark ? const Color(0xFF334155) : const Color(0xFFE2E8F0),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              const Icon(Icons.email_outlined, size: 16, color: AppTheme.primaryColor),
                              const SizedBox(width: 6),
                              const Text('Email Source Details', style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold)),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Text('Subject: ${msg.subject}', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                          const SizedBox(height: 4),
                          Text('Sender: ${msg.sender}', style: TextStyle(fontSize: 12, color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B))),
                          const SizedBox(height: 4),
                          Text('Received: $dateStr', style: TextStyle(fontSize: 12, color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B))),
                        ],
                      ),
                    ),

                    const SizedBox(height: 24),

                    // Action Buttons
                    Row(
                      children: [
                        OutlinedButton.icon(
                          onPressed: () {
                            Navigator.of(ctx).pop();
                            _confirmDelete(msg);
                          },
                          icon: const Icon(Icons.delete_outline_rounded, size: 16, color: AppTheme.errorColor),
                          label: const Text('Delete', style: TextStyle(color: AppTheme.errorColor)),
                        ),
                        const Spacer(),
                        OutlinedButton.icon(
                          onPressed: () {
                            Navigator.of(ctx).pop();
                            _showDocumentPreviewModal(msg);
                          },
                          icon: const Icon(Icons.visibility_rounded, size: 16),
                          label: const Text('Preview Document'),
                        ),
                        const SizedBox(width: 10),
                        ElevatedButton.icon(
                          onPressed: isProcessing
                              ? null
                              : () async {
                                  Navigator.of(ctx).pop();
                                  await _processAndNavigate(msg);
                                },
                          icon: isProcessing
                              ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                              : const Icon(Icons.play_arrow_rounded, size: 18),
                          label: Text(isProcessing ? 'Processing...' : 'Process to Workspace'),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final intProvider = Provider.of<IntegrationProvider>(context);
    final messages = intProvider.inboxMessages;

    final isMobile = MediaQuery.of(context).size.width < 750;

    // Classification origin counts
    final indianCount = messages.where((m) => m.isIndian).length;
    final foreignCount = messages.where((m) => m.isForeign).length;

    // Filtered messages list
    final filteredMessages = messages.where((m) {
      if (_selectedOrigin == 'indian' && !m.isIndian) return false;
      if (_selectedOrigin == 'foreign' && !m.isForeign) return false;
      if (_searchQuery.trim().isNotEmpty) {
        final q = _searchQuery.trim().toLowerCase();
        final subj = m.subject.toLowerCase();
        final sender = m.sender.toLowerCase();
        final fname = (m.fileName ?? '').toLowerCase();
        final docType = (m.documentType ?? '').toLowerCase();
        if (!subj.contains(q) && !sender.contains(q) && !fname.contains(q) && !docType.contains(q)) {
          return false;
        }
      }
      return true;
    }).toList();

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Padding(
        padding: EdgeInsets.symmetric(
          horizontal: isMobile ? 16 : 32,
          vertical: isMobile ? 18 : 28,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header Bar
            if (isMobile) ...[
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Email Inbox Ingestion',
                    style: TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.w800,
                      letterSpacing: -0.5,
                      color: isDark ? Colors.white : const Color(0xFF0F172A),
                    ),
                  ),
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      IconButton(
                        onPressed: intProvider.isLoading ? null : () => intProvider.refreshInbox(),
                        icon: const Icon(Icons.refresh_rounded, size: 20),
                        tooltip: 'Refresh',
                        style: IconButton.styleFrom(
                          backgroundColor: isDark ? AppTheme.darkCard : Colors.white,
                        ),
                      ),
                      const SizedBox(width: 6),
                      IconButton(
                        onPressed: intProvider.isSyncingEmail ? null : () => intProvider.syncEmailNow(),
                        icon: intProvider.isSyncingEmail
                            ? const SizedBox(height: 14, width: 14, child: CircularProgressIndicator(strokeWidth: 2))
                            : const Icon(Icons.sync_rounded, size: 20, color: AppTheme.primaryLight),
                        tooltip: 'Sync Inbox',
                        style: IconButton.styleFrom(
                          backgroundColor: isDark ? AppTheme.darkCard : Colors.white,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                'Classifies and separates Indian vs Foreign/International invoices',
                style: TextStyle(
                  fontSize: 12.5,
                  color: isDark ? AppTheme.darkTextSecondary : AppTheme.lightTextSecondary,
                ),
              ),
            ] else ...[
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            const Text('Email Inbox Ingestion', style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
                            const SizedBox(width: 12),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                              decoration: BoxDecoration(
                                color: const Color(0xFF10B981).withValues(alpha: 0.12),
                                borderRadius: BorderRadius.circular(12),
                                border: Border.all(color: const Color(0xFF10B981).withValues(alpha: 0.3)),
                              ),
                              child: Text(
                                '🇮🇳 $indianCount Indian',
                                style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.bold, color: Color(0xFF10B981)),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                              decoration: BoxDecoration(
                                color: const Color(0xFF6366F1).withValues(alpha: 0.12),
                                borderRadius: BorderRadius.circular(12),
                                border: Border.all(color: const Color(0xFF6366F1).withValues(alpha: 0.3)),
                              ),
                              child: Text(
                                '🌐 $foreignCount Foreign',
                                style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.bold, color: Color(0xFF6366F1)),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Visual AI classification separates domestic Indian GST invoices and foreign/international bills automatically',
                          style: TextStyle(fontSize: 13, color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 14),
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      OutlinedButton.icon(
                        onPressed: intProvider.isLoading ? null : () => intProvider.refreshInbox(),
                        icon: const Icon(Icons.refresh_rounded, size: 18),
                        label: const Text('Refresh'),
                      ),
                      const SizedBox(width: 10),
                      ElevatedButton.icon(
                        onPressed: intProvider.isSyncingEmail ? null : () => intProvider.syncEmailNow(),
                        icon: intProvider.isSyncingEmail
                            ? const SizedBox(height: 14, width: 14, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                            : const Icon(Icons.sync_rounded, size: 18),
                        label: const Text('Sync Inbox Now'),
                      ),
                    ],
                  ),
                ],
              ),
            ],

            const SizedBox(height: 18),

            // Origin Filter Tabs & Search Bar
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: isDark ? const Color(0xFF1E293B) : const Color(0xFFF1F5F9),
                borderRadius: BorderRadius.circular(14),
                border: Border.all(
                  color: isDark ? const Color(0xFF334155) : const Color(0xFFE2E8F0),
                ),
              ),
              child: Flex(
                direction: isMobile ? Axis.vertical : Axis.horizontal,
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  // Origin Tabs
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: [
                      _buildOriginTab(
                        id: 'all',
                        label: 'All Invoices',
                        count: messages.length,
                        icon: Icons.all_inbox_rounded,
                        isDark: isDark,
                      ),
                      _buildOriginTab(
                        id: 'indian',
                        label: '🇮🇳 Indian Invoices',
                        count: indianCount,
                        icon: Icons.flag_rounded,
                        isDark: isDark,
                        badgeColor: const Color(0xFF10B981),
                      ),
                      _buildOriginTab(
                        id: 'foreign',
                        label: '🌐 Foreign / International',
                        count: foreignCount,
                        icon: Icons.public_rounded,
                        isDark: isDark,
                        badgeColor: const Color(0xFF6366F1),
                      ),
                    ],
                  ),
                  if (isMobile) const SizedBox(height: 8),

                  // Search Field
                  ConstrainedBox(
                    constraints: BoxConstraints(maxWidth: isMobile ? double.infinity : 280),
                    child: TextField(
                      controller: _searchController,
                      onChanged: (val) => setState(() => _searchQuery = val),
                      decoration: InputDecoration(
                        isDense: true,
                        hintText: 'Search by sender, subject...',
                        hintStyle: TextStyle(fontSize: 12.5, color: isDark ? const Color(0xFF64748B) : const Color(0xFF94A3B8)),
                        prefixIcon: const Icon(Icons.search_rounded, size: 18),
                        suffixIcon: _searchQuery.isNotEmpty
                            ? IconButton(
                                icon: const Icon(Icons.clear_rounded, size: 16),
                                onPressed: () {
                                  _searchController.clear();
                                  setState(() => _searchQuery = '');
                                },
                              )
                            : null,
                        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                        filled: true,
                        fillColor: isDark ? const Color(0xFF0F172A) : Colors.white,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(10),
                          borderSide: BorderSide.none,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 16),

            // Content Body
            Expanded(
              child: intProvider.isLoading && messages.isEmpty
                  ? ListView.builder(
                      itemCount: 5,
                      itemBuilder: (_, __) => const ListItemSkeleton(),
                    )
                  : messages.isEmpty
                      ? GlassCard(
                          padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 48),
                          child: Center(
                            child: ConstrainedBox(
                              constraints: const BoxConstraints(maxWidth: 480),
                              child: Column(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Container(
                                    padding: const EdgeInsets.all(16),
                                    decoration: BoxDecoration(
                                      color: AppTheme.primaryColor.withValues(alpha: 0.1),
                                      shape: BoxShape.circle,
                                    ),
                                    child: Icon(
                                      Icons.mark_email_read_outlined,
                                      size: 40,
                                      color: isDark ? AppTheme.primaryLight : AppTheme.primaryColor,
                                    ),
                                  ),
                                  const SizedBox(height: 18),
                                  Text(
                                    'No Invoices in Inbox',
                                    style: TextStyle(
                                      fontSize: 18,
                                      fontWeight: FontWeight.w800,
                                      letterSpacing: -0.3,
                                      color: isDark ? Colors.white : const Color(0xFF0F172A),
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  Text(
                                    'Invoices and purchase bills sent to your connected mailbox will automatically be classified into Indian vs Foreign categories and presented here.',
                                    textAlign: TextAlign.center,
                                    style: TextStyle(
                                      fontSize: 13,
                                      height: 1.5,
                                      color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B),
                                    ),
                                  ),
                                  const SizedBox(height: 20),
                                  ElevatedButton.icon(
                                    onPressed: intProvider.isSyncingEmail ? null : () => intProvider.syncEmailNow(),
                                    icon: intProvider.isSyncingEmail
                                        ? const SizedBox(height: 14, width: 14, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                                        : const Icon(Icons.sync_rounded, size: 18),
                                    label: Text(intProvider.isSyncingEmail ? 'Syncing Mailbox...' : 'Sync Inbox Now'),
                                    style: ElevatedButton.styleFrom(
                                      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        )
                      : filteredMessages.isEmpty
                          ? GlassCard(
                              padding: const EdgeInsets.all(36),
                              child: Center(
                                child: Column(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Icon(
                                      _selectedOrigin == 'foreign' ? Icons.public_off_rounded : Icons.search_off_rounded,
                                      size: 48,
                                      color: isDark ? const Color(0xFF64748B) : const Color(0xFF94A3B8),
                                    ),
                                    const SizedBox(height: 14),
                                    Text(
                                      _selectedOrigin == 'foreign'
                                          ? 'No Foreign Invoices Found'
                                          : _selectedOrigin == 'indian'
                                              ? 'No Indian Invoices Found'
                                              : 'No Invoices Match Your Search',
                                      style: TextStyle(
                                        fontSize: 16,
                                        fontWeight: FontWeight.bold,
                                        color: isDark ? Colors.white : const Color(0xFF0F172A),
                                      ),
                                    ),
                                    const SizedBox(height: 6),
                                    Text(
                                      _selectedOrigin == 'foreign'
                                          ? 'All ${messages.length} currently staged invoices are classified as Indian domestic invoices.'
                                          : _selectedOrigin == 'indian'
                                              ? 'All ${messages.length} currently staged invoices are classified as Foreign / International invoices.'
                                              : 'Try adjusting your search query or reset filters.',
                                      textAlign: TextAlign.center,
                                      style: TextStyle(
                                        fontSize: 12.5,
                                        color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B),
                                      ),
                                    ),
                                    const SizedBox(height: 16),
                                    OutlinedButton.icon(
                                      onPressed: () {
                                        setState(() {
                                          _selectedOrigin = 'all';
                                          _searchQuery = '';
                                          _searchController.clear();
                                        });
                                      },
                                      icon: const Icon(Icons.filter_alt_off_rounded, size: 16),
                                      label: const Text('Show All Invoices'),
                                    ),
                                  ],
                                ),
                              ),
                            )
                          : ListView.builder(
                              itemCount: filteredMessages.length,
                              itemBuilder: (context, index) {
                                final msg = filteredMessages[index];
                                final date = msg.date != null ? DateFormat('dd MMM, hh:mm a').format(msg.date!) : '';
                                final isPdf = (msg.fileName?.toLowerCase().endsWith('.pdf') ?? true) || (msg.mimeType?.contains('pdf') ?? true);
                                final isProcessing = _processingMap[msg.id] == true;

                                return GlassCard(
                                  margin: const EdgeInsets.only(bottom: 12),
                                  padding: EdgeInsets.all(isMobile ? 12 : 16),
                                  child: isMobile
                                      ? Column(
                                          crossAxisAlignment: CrossAxisAlignment.start,
                                          children: [
                                            Row(
                                              children: [
                                                Container(
                                                  padding: const EdgeInsets.all(8),
                                                  decoration: BoxDecoration(
                                                    color: isPdf
                                                        ? const Color(0xFFEF4444).withValues(alpha: 0.12)
                                                        : AppTheme.primaryColor.withValues(alpha: 0.12),
                                                    borderRadius: BorderRadius.circular(8),
                                                  ),
                                                  child: Icon(
                                                    isPdf ? Icons.picture_as_pdf_rounded : Icons.image_rounded,
                                                    color: isPdf ? const Color(0xFFEF4444) : AppTheme.primaryColor,
                                                    size: 20,
                                                  ),
                                                ),
                                                const SizedBox(width: 10),
                                                Expanded(
                                                  child: Text(
                                                    msg.fileName ?? msg.subject,
                                                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                                                    overflow: TextOverflow.ellipsis,
                                                  ),
                                                ),
                                                const SizedBox(width: 6),
                                                _buildOriginBadge(msg),
                                              ],
                                            ),
                                            const SizedBox(height: 8),
                                            Text(
                                              'Subject: ${msg.subject}',
                                              style: TextStyle(fontSize: 12, color: isDark ? const Color(0xFFCBD5E1) : const Color(0xFF334155)),
                                              maxLines: 1,
                                              overflow: TextOverflow.ellipsis,
                                            ),
                                            const SizedBox(height: 2),
                                            Text(
                                              'From: ${msg.sender} • $date',
                                              style: TextStyle(fontSize: 11, color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
                                              maxLines: 1,
                                              overflow: TextOverflow.ellipsis,
                                            ),
                                            const SizedBox(height: 10),
                                            Row(
                                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                              children: [
                                                Row(
                                                  mainAxisSize: MainAxisSize.min,
                                                  children: [
                                                    IconButton(
                                                      tooltip: 'Inspect Details',
                                                      visualDensity: VisualDensity.compact,
                                                      icon: const Icon(Icons.info_outline_rounded, size: 18),
                                                      onPressed: () => _showDocumentDetailsModal(msg),
                                                    ),
                                                    IconButton(
                                                      tooltip: 'Preview Document',
                                                      visualDensity: VisualDensity.compact,
                                                      icon: const Icon(Icons.visibility_outlined, size: 18, color: AppTheme.primaryColor),
                                                      onPressed: () => _showDocumentPreviewModal(msg),
                                                    ),
                                                    IconButton(
                                                      tooltip: 'Delete',
                                                      visualDensity: VisualDensity.compact,
                                                      icon: const Icon(Icons.delete_outline_rounded, size: 18, color: AppTheme.errorColor),
                                                      onPressed: () => _confirmDelete(msg),
                                                    ),
                                                  ],
                                                ),
                                                ElevatedButton.icon(
                                                  style: ElevatedButton.styleFrom(
                                                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                                    textStyle: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600),
                                                  ),
                                                  onPressed: isProcessing ? null : () => _processAndNavigate(msg),
                                                  icon: isProcessing
                                                      ? const SizedBox(width: 10, height: 10, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                                                      : const Icon(Icons.arrow_forward_rounded, size: 13),
                                                  label: Text(isProcessing ? 'Processing...' : 'Process'),
                                                ),
                                              ],
                                            ),
                                          ],
                                        )
                                      : Row(
                                          crossAxisAlignment: CrossAxisAlignment.start,
                                          children: [
                                            // Leading Document Icon
                                            Container(
                                              padding: const EdgeInsets.all(12),
                                              decoration: BoxDecoration(
                                                color: isPdf
                                                    ? const Color(0xFFEF4444).withValues(alpha: 0.12)
                                                    : AppTheme.primaryColor.withValues(alpha: 0.12),
                                                borderRadius: BorderRadius.circular(10),
                                              ),
                                              child: Icon(
                                                isPdf ? Icons.picture_as_pdf_rounded : Icons.image_rounded,
                                                color: isPdf ? const Color(0xFFEF4444) : AppTheme.primaryColor,
                                                size: 24,
                                              ),
                                            ),
                                            const SizedBox(width: 14),

                                            // Main Info
                                            Expanded(
                                              child: Column(
                                                crossAxisAlignment: CrossAxisAlignment.start,
                                                children: [
                                                  Row(
                                                    children: [
                                                      Expanded(
                                                        child: Text(
                                                          msg.fileName ?? msg.subject,
                                                          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                                                          overflow: TextOverflow.ellipsis,
                                                        ),
                                                      ),
                                                      const SizedBox(width: 8),
                                                      _buildOriginBadge(msg),
                                                      const SizedBox(width: 6),
                                                      Container(
                                                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                                        decoration: BoxDecoration(
                                                          color: AppTheme.accentColor.withValues(alpha: 0.15),
                                                          borderRadius: BorderRadius.circular(4),
                                                        ),
                                                        child: Text(
                                                          msg.documentType ?? 'INVOICE',
                                                          style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: AppTheme.accentColor),
                                                        ),
                                                      ),
                                                    ],
                                                  ),
                                                  const SizedBox(height: 6),
                                                  Text(
                                                    'From: ${msg.sender} • $date • ${_formatFileSize(msg.fileSize)}',
                                                    style: TextStyle(fontSize: 12, color: isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
                                                  ),
                                                ],
                                              ),
                                            ),
                                            const SizedBox(width: 14),

                                            // Quick Action Buttons
                                            Column(
                                              crossAxisAlignment: CrossAxisAlignment.end,
                                              children: [
                                                Row(
                                                  mainAxisSize: MainAxisSize.min,
                                                  children: [
                                                    IconButton(
                                                      tooltip: 'Inspect Details',
                                                      icon: const Icon(Icons.info_outline_rounded, size: 20),
                                                      onPressed: () => _showDocumentDetailsModal(msg),
                                                    ),
                                                    IconButton(
                                                      tooltip: 'Preview Document',
                                                      icon: const Icon(Icons.visibility_outlined, size: 20, color: AppTheme.primaryColor),
                                                      onPressed: () => _showDocumentPreviewModal(msg),
                                                    ),
                                                    IconButton(
                                                      tooltip: 'Delete',
                                                      icon: const Icon(Icons.delete_outline_rounded, size: 20, color: AppTheme.errorColor),
                                                      onPressed: () => _confirmDelete(msg),
                                                    ),
                                                  ],
                                                ),
                                                const SizedBox(height: 4),
                                                ElevatedButton.icon(
                                                  style: ElevatedButton.styleFrom(
                                                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                                                    textStyle: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                                                  ),
                                                  onPressed: isProcessing ? null : () => _processAndNavigate(msg),
                                                  icon: isProcessing
                                                      ? const SizedBox(width: 12, height: 12, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                                                      : const Icon(Icons.arrow_forward_rounded, size: 14),
                                                  label: Text(isProcessing ? 'Processing...' : 'Process Invoice'),
                                                ),
                                              ],
                                            ),
                                          ],
                                        ),
                                );
                              },
                            ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildOriginTab({
    required String id,
    required String label,
    required int count,
    required IconData icon,
    required bool isDark,
    Color? badgeColor,
  }) {
    final isSelected = _selectedOrigin == id;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () => setState(() => _selectedOrigin = id),
        borderRadius: BorderRadius.circular(10),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          decoration: BoxDecoration(
            color: isSelected
                ? (badgeColor ?? AppTheme.primaryColor).withValues(alpha: 0.18)
                : Colors.transparent,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: isSelected
                  ? (badgeColor ?? AppTheme.primaryColor).withValues(alpha: 0.5)
                  : Colors.transparent,
              width: 1,
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                icon,
                size: 15,
                color: isSelected
                    ? (badgeColor ?? AppTheme.primaryLight)
                    : (isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
              ),
              const SizedBox(width: 6),
              Text(
                label,
                style: TextStyle(
                  fontSize: 12.5,
                  fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                  color: isSelected
                      ? (isDark ? Colors.white : const Color(0xFF0F172A))
                      : (isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B)),
                ),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: isSelected
                      ? (badgeColor ?? AppTheme.primaryColor)
                      : (isDark ? const Color(0xFF334155) : const Color(0xFFCBD5E1)),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  '$count',
                  style: TextStyle(
                    fontSize: 10.5,
                    fontWeight: FontWeight.bold,
                    color: isSelected ? Colors.white : (isDark ? Colors.white70 : const Color(0xFF334155)),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildOriginBadge(EmailMessage msg) {
    final isForeign = msg.isForeign;
    final color = isForeign ? const Color(0xFF6366F1) : const Color(0xFF10B981);
    final label = isForeign ? '🌐 Foreign (${msg.currency ?? "USD"})' : '🇮🇳 Indian (INR)';

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            isForeign ? Icons.public_rounded : Icons.flag_rounded,
            size: 11,
            color: color,
          ),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              fontSize: 10.5,
              fontWeight: FontWeight.w700,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}
