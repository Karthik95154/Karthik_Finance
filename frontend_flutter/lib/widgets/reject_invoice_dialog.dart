import 'package:flutter/material.dart';

class RejectInvoiceDialog extends StatefulWidget {
  final Function(String reason) onConfirm;

  const RejectInvoiceDialog({super.key, required this.onConfirm});

  @override
  State<RejectInvoiceDialog> createState() => _RejectInvoiceDialogState();
}

class _RejectInvoiceDialogState extends State<RejectInvoiceDialog> {
  final _reasonController = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  bool _isSubmitting = false;

  final List<String> _quickReasons = [
    'GSTIN does not match invoice header',
    'Mathematical sum mismatch > ₹10.00',
    'Duplicate invoice number for vendor',
    'Bank account details unverified / mismatch',
    'Invalid SAC / HSN tax rate specified',
    'Invoice belongs to closed accounting period',
  ];

  @override
  void dispose() {
    _reasonController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return AlertDialog(
      title: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.red.withOpacity(0.15),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Icon(Icons.cancel_outlined, color: Colors.redAccent, size: 20),
          ),
          const SizedBox(width: 12),
          const Text('Reject Invoice', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
        ],
      ),
      content: SizedBox(
        width: 480,
        child: Form(
          key: _formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Please provide an audit rejection rationale. This will be permanently recorded in the immutable audit trail.',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.textTheme.bodySmall?.color,
                ),
              ),
              const SizedBox(height: 14),
              // Quick reason chips
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: _quickReasons.map((r) {
                  return ActionChip(
                    label: Text(r, style: const TextStyle(fontSize: 11)),
                    onPressed: () {
                      _reasonController.text = r;
                    },
                  );
                }).toList(),
              ),
              const SizedBox(height: 14),
              TextFormField(
                controller: _reasonController,
                maxLines: 3,
                decoration: InputDecoration(
                  labelText: 'Rejection Reason (Required)',
                  hintText: 'Describe specific statutory or accounting defect...',
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                ),
                validator: (val) {
                  if (val == null || val.trim().isEmpty) {
                    return 'Rejection reason is required.';
                  }
                  return null;
                },
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: _isSubmitting ? null : () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          onPressed: _isSubmitting
              ? null
              : () async {
                  if (_formKey.currentState?.validate() == true) {
                    setState(() => _isSubmitting = true);
                    await widget.onConfirm(_reasonController.text.trim());
                    if (mounted) Navigator.of(context).pop();
                  }
                },
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.redAccent,
            foregroundColor: Colors.white,
          ),
          child: _isSubmitting
              ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
              : const Text('Confirm Rejection'),
        ),
      ],
    );
  }
}
