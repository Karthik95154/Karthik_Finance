import 'package:flutter/material.dart';
import '../models/invoice_models.dart';

class AddVendorBanner extends StatelessWidget {
  final InvoiceVendorStatusResponse? vendorStatus;
  final VoidCallback onAddVendor;
  final bool isAdding;

  const AddVendorBanner({
    super.key,
    this.vendorStatus,
    required this.onAddVendor,
    this.isAdding = false,
  });

  @override
  Widget build(BuildContext context) {
    final status = vendorStatus;
    if (status == null || !status.isZohoConnected) {
      return const SizedBox.shrink();
    }

    final isMatched = status.matchStatus == 'MATCHED';
    final vendorName = status.invoiceVendor['vendor_name']?.toString() ?? 'Vendor';
    final gstin = status.invoiceVendor['vendor_gstin']?.toString();

    if (isMatched) {
      return Container(
        margin: const EdgeInsets.only(bottom: 16),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: const Color(0xFF10B981).withOpacity(0.08),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: const Color(0xFF10B981).withOpacity(0.3)),
        ),
        child: Row(
          children: [
            const Icon(Icons.check_circle, color: const Color(0xFF10B981), size: 20),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                'Zoho Books Vendor Verified: Matched "${status.matchedVendor?.contactName ?? vendorName}" (Contact ID: ${status.matchedVendor?.contactId ?? "Sync OK"})',
                style: const TextStyle(fontSize: 12, color: const Color(0xFF10B981), fontWeight: FontWeight.w600),
              ),
            ),
          ],
        ),
      );
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: Colors.amber.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.amber.withOpacity(0.4)),
      ),
      child: Row(
        children: [
          const Icon(Icons.person_add_alt_1_outlined, color: Colors.amber, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Vendor "$vendorName" is not found in Zoho Books.',
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Colors.amber),
                ),
                if (gstin != null && gstin.isNotEmpty)
                  Text(
                    'GSTIN: $gstin will be used to auto-create contact in Zoho.',
                    style: TextStyle(fontSize: 11, color: Colors.amber.shade200),
                  ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          ElevatedButton.icon(
            onPressed: isAdding ? null : onAddVendor,
            icon: isAdding
                ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.black))
                : const Icon(Icons.add, size: 16),
            label: const Text('Add to Zoho', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.amber,
              foregroundColor: Colors.black,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            ),
          ),
        ],
      ),
    );
  }
}
