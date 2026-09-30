import 'package:flutter/material.dart';

class CreateCoaDialog extends StatefulWidget {
  final String? initialAccountName;
  final Function(String name, String type, String? code, String? description) onConfirm;

  const CreateCoaDialog({
    super.key,
    this.initialAccountName,
    required this.onConfirm,
  });

  @override
  State<CreateCoaDialog> createState() => _CreateCoaDialogState();
}

class _CreateCoaDialogState extends State<CreateCoaDialog> {
  final _formKey = GlobalKey<FormState>();
  late TextEditingController _nameController;
  final _codeController = TextEditingController();
  final _descController = TextEditingController();
  String _selectedType = 'Expense';
  bool _isSubmitting = false;

  final List<String> _accountTypes = [
    'Expense',
    'Cost of Goods Sold',
    'Fixed Asset',
    'Other Current Asset',
    'Other Current Liability',
    'Other Expense',
    'Bank',
  ];

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(text: widget.initialAccountName ?? '');
  }

  @override
  void dispose() {
    _nameController.dispose();
    _codeController.dispose();
    _descController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.blue.withOpacity(0.15),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Icon(Icons.add_card_outlined, color: Colors.blue, size: 20),
          ),
          const SizedBox(width: 12),
          const Text('Create Account in Zoho COA', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 17)),
        ],
      ),
      content: SizedBox(
        width: 460,
        child: Form(
          key: _formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: _nameController,
                decoration: InputDecoration(
                  labelText: 'Account Name *',
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                ),
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Account name is required' : null,
              ),
              const SizedBox(height: 14),
              DropdownButtonFormField<String>(
                value: _selectedType,
                decoration: InputDecoration(
                  labelText: 'Account Type *',
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                ),
                items: _accountTypes.map((t) => DropdownMenuItem(value: t, child: Text(t))).toList(),
                onChanged: (v) {
                  if (v != null) setState(() => _selectedType = v);
                },
              ),
              const SizedBox(height: 14),
              TextFormField(
                controller: _codeController,
                decoration: InputDecoration(
                  labelText: 'Account Code (Optional)',
                  hintText: 'e.g. 5010',
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                ),
              ),
              const SizedBox(height: 14),
              TextFormField(
                controller: _descController,
                decoration: InputDecoration(
                  labelText: 'Description (Optional)',
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                ),
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
                    await widget.onConfirm(
                      _nameController.text.trim(),
                      _selectedType,
                      _codeController.text.trim().isNotEmpty ? _codeController.text.trim() : null,
                      _descController.text.trim().isNotEmpty ? _descController.text.trim() : null,
                    );
                    if (mounted) Navigator.of(context).pop();
                  }
                },
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.blue,
            foregroundColor: Colors.white,
          ),
          child: _isSubmitting
              ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
              : const Text('Create in Zoho'),
        ),
      ],
    );
  }
}
