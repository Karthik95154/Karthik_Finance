import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/models/auth_models.dart';
import 'package:frontend_flutter/models/audit_models.dart';
import 'package:frontend_flutter/models/dashboard_models.dart';
import 'package:frontend_flutter/models/health_models.dart';
import 'package:frontend_flutter/models/invoice_models.dart';
import 'package:frontend_flutter/models/integration_models.dart';
import 'package:frontend_flutter/providers/invoice_provider.dart';

void main() {
  group('Model Serialization Tests', () {
    test('User serialization', () {
      final json = {
        'id': 1,
        'email': 'accountant@sakshifinance.com',
        'full_name': 'Karthik Mullapati',
        'role': 'admin',
        'is_active': true,
      };

      final user = User.fromJson(json);
      expect(user.id, 1);
      expect(user.email, 'accountant@sakshifinance.com');
      expect(user.fullName, 'Karthik Mullapati');
      expect(user.role, 'admin');

      final serialized = user.toJson();
      expect(serialized['email'], 'accountant@sakshifinance.com');
    });

    test('ExtractedInvoiceData and LineItem serialization', () {
      final json = {
        'invoice_number': 'INV-2026-009',
        'invoice_date': '2026-09-20',
        'vendor_name': 'Acme Services Pvt Ltd',
        'vendor_gstin': '36ABCDE1234F1Z5',
        'taxable_amount': 50000.0,
        'cgst_amount': 4500.0,
        'sgst_amount': 4500.0,
        'total_amount': 59000.0,
        'line_items': [
          {
            'line_index': 1,
            'description': 'Cloud Software Architecture Consulting',
            'hsn_code': '998314',
            'quantity': 1.0,
            'unit_price': 50000.0,
            'taxable_amount': 50000.0,
            'gst_rate': 18.0,
            'cgst_rate': 9.0,
            'cgst_amount': 4500.0,
            'sgst_rate': 9.0,
            'sgst_amount': 4500.0,
            'total': 59000.0,
          }
        ],
      };

      final invoice = ExtractedInvoiceData.fromJson(json);
      expect(invoice.invoiceNumber, 'INV-2026-009');
      expect(invoice.vendorName, 'Acme Services Pvt Ltd');
      expect(invoice.lineItems.length, 1);
      expect(invoice.lineItems.first.hsnCode, '998314');
      expect(invoice.totalAmount, 59000.0);
      expect(invoice.vendorPan, 'ABCDE1234F'); // Derived from vendor_gstin
      expect(invoice.placeOfSupply, '36 - Telangana'); // Derived from 36 state code
    });

    test('ExtractedInvoiceData complex nested VLM structure with PAN & POS derivation', () {
      final nestedVlm = {
        'data': {
          'invoice_details': {
            'invoice_number': 'TAX-2026-9921',
            'invoice_date': '15-Aug-2026',
            'due_date': '30-Aug-2026',
            'po_number': 'PO-8820',
            'currency': 'INR',
          },
          'vendor_details': {
            'vendor_name': 'Tata Consultancy Services',
            'vendor_gstin': '27AABCT2345C1Z8',
            'vendor_address': 'TCS House, Raveline Street, Mumbai',
            'vendor_phone': '+91 22 6778 9999',
            'vendor_email': 'billing@tcs.com',
            'bank_details': {
              'bank_name': 'State Bank of India',
              'account_number': '10987654321',
              'ifsc_code': 'SBIN0000300',
            },
          },
          'customer_details': {
            'customer_name': 'Sakshi Finance Enterprise Ltd',
            'customer_gstin': '36AAECS6056C1ZQ',
            'customer_address': 'HITEC City, Hyderabad, Telangana',
          },
          'financial_details': {
            'subtotal': 200000.0,
            'taxable_amount': 200000.0,
            'igst_amount': 36000.0,
            'total_amount': 236000.0,
          },
          'line_items': [
            {
              'description': 'AI Cloud FinOps Platform Engineering',
              'hsn_sac_code': '998313',
              'quantity': 2.0,
              'unit_price': 100000.0,
              'taxable_amount': 200000.0,
              'igst_rate': 18.0,
              'igst_amount': 36000.0,
              'total': 236000.0,
            }
          ]
        }
      };

      final inv = ExtractedInvoiceData.fromJson(nestedVlm);
      expect(inv.invoiceNumber, 'TAX-2026-9921');
      expect(inv.invoiceDate, '15-Aug-2026');
      expect(inv.dueDate, '30-Aug-2026');
      expect(inv.poNumber, 'PO-8820');
      expect(inv.vendorName, 'Tata Consultancy Services');
      expect(inv.vendorGstin, '27AABCT2345C1Z8');
      expect(inv.vendorPan, 'AABCT2345C'); // Auto-extracted from GSTIN
      expect(inv.customerName, 'Sakshi Finance Enterprise Ltd');
      expect(inv.customerGstin, '36AAECS6056C1ZQ');
      expect(inv.customerPan, 'AAECS6056C'); // Auto-extracted from GSTIN
      expect(inv.placeOfSupply, '36 - Telangana'); // Auto-derived from Customer GSTIN (36)
      expect(inv.bankDetails?.bankName, 'State Bank of India');
      expect(inv.bankDetails?.accountNumber, '10987654321');
      expect(inv.lineItems.length, 1);
      expect(inv.lineItems.first.hsnCode, '998313');
      expect(inv.lineItems.first.gstRate, 18.0);
      expect(inv.totalAmount, 236000.0);
    });

    test('Invoice.fromJson full VLM response integration', () {
      final backendResponse = {
        'id': 'b130dbd8-9df2-4fbc-b40b-b38466184852',
        'status': 'PENDING_REVIEW',
        'approval_status': 'PENDING_REVIEW',
        'current_vlm_output': {
          'invoice_number': 'INV-AUTO-771',
          'invoice_date': '2026-09-01',
          'vendor_name': 'Zomato Media Ltd',
          'vendor_gstin': '07AABCB1234A1Z1',
          'customer_name': 'Sakshi Finance Enterprise',
          'customer_gstin': '36AAECS6056C1ZQ',
          'taxable_amount': 15000.0,
          'cgst_amount': 1350.0,
          'sgst_amount': 1350.0,
          'total_amount': 17700.0,
          'line_items': [
            {
              'description': 'Corporate Meal Benefits Voucher',
              'hsn_code': '996331',
              'quantity': 15.0,
              'unit_price': 1000.0,
              'taxable_amount': 15000.0,
              'cgst_rate': 9.0,
              'cgst_amount': 1350.0,
              'sgst_rate': 9.0,
              'sgst_amount': 1350.0,
              'total': 17700.0,
            }
          ]
        },
        'current_accounting_output': {
          'tds_final': {
            'applicable': true,
            'approved_tds_section': '194C',
            'approved_tds_rate': 2.0,
            'tds_base_amount': 15000.0,
            'extracted_tds_amount': 300.0,
            'nature_of_payment': 'Catering and meal voucher services',
          },
          'journal_entry': {
            'journal_number': 'JV-2026-0991',
            'lines': [
              {
                'account_code': '5020',
                'account_name': 'Staff Welfare Expense',
                'debit': 15000.0,
                'credit': 0.0,
              },
              {
                'account_code': '1050',
                'account_name': 'Input CGST',
                'debit': 1350.0,
                'credit': 0.0,
              },
              {
                'account_code': '1051',
                'account_name': 'Input SGST',
                'debit': 1350.0,
                'credit': 0.0,
              },
              {
                'account_code': '2020',
                'account_name': 'TDS Payable 194C',
                'debit': 0.0,
                'credit': 300.0,
              },
              {
                'account_code': '2010',
                'account_name': 'Zomato Media Ltd (AP)',
                'debit': 0.0,
                'credit': 17400.0,
              },
            ]
          }
        }
      };

      final invoice = Invoice.fromJson(backendResponse);
      expect(invoice.extractedData?.invoiceNumber, 'INV-AUTO-771');
      expect(invoice.extractedData?.vendorName, 'Zomato Media Ltd');
      expect(invoice.extractedData?.vendorPan, 'AABCB1234A');
      expect(invoice.extractedData?.customerPan, 'AAECS6056C');
      expect(invoice.extractedData?.placeOfSupply, '36 - Telangana');
      expect(invoice.tdsResult?.applicable, true);
      expect(invoice.tdsResult?.tdsSection, '194C');
      expect(invoice.tdsResult?.tdsRate, 2.0);
      expect(invoice.tdsResult?.tdsAmount, 300.0);
      expect(invoice.journalEntry?.isBalanced, true);
      expect(invoice.journalEntry?.totalDebit, 17700.0);
      expect(invoice.journalEntry?.totalCredit, 17700.0);
    });

    test('TdsResult serialization', () {
      final json = {
        'applicable': true,
        'tds_section': '194J',
        'tds_rate': 10.0,
        'tds_base_amount': 50000.0,
        'tds_amount': 5000.0,
      };

      final tds = TdsResult.fromJson(json);
      expect(tds.applicable, true);
      expect(tds.tdsSection, '194J');
      expect(tds.tdsRate, 10.0);
      expect(tds.tdsAmount, 5000.0);
    });

    test('JournalEntry serialization and balance check', () {
      final json = {
        'journal_number': 'JRN-1001',
        'date': '2026-09-20',
        'lines': [
          {
            'account_code': 'EXP-100',
            'account_name': 'Professional Fees',
            'debit': 50000.0,
            'credit': 0.0,
          },
          {
            'account_code': 'GST-IN',
            'account_name': 'Input GST',
            'debit': 9000.0,
            'credit': 0.0,
          },
          {
            'account_code': 'TDS-PAY',
            'account_name': 'TDS Payable 194J',
            'debit': 0.0,
            'credit': 5000.0,
          },
          {
            'account_code': 'AP-VEND',
            'account_name': 'Accounts Payable',
            'debit': 0.0,
            'credit': 54000.0,
          }
        ]
      };

      final journal = JournalEntry.fromJson(json);
      expect(journal.lines.length, 4);
      expect(journal.totalDebit, 59000.0);
      expect(journal.totalCredit, 59000.0);
      expect(journal.isBalanced, true);
    });

    test('DashboardMetrics serialization', () {
      final json = {
        'total_invoices': 45,
        'pending_review': 5,
        'auto_approved': 30,
        'exported_zoho': 28,
        'failed_count': 2,
        'total_amount_processed': 1500000.0,
        'average_confidence': 0.96,
      };

      final metrics = DashboardMetrics.fromJson(json);
      expect(metrics.totalInvoices, 45);
      expect(metrics.pendingReview, 5);
      expect(metrics.exportedZoho, 28);
    });

    test('ZohoConnectionStatus serialization', () {
      final json = {
        'is_connected': true,
        'organization_name': 'Sakshi Global Corp',
        'organization_id': 'ORG-99881',
      };

      final zoho = ZohoConnectionStatus.fromJson(json);
      expect(zoho.isConnected, true);
      expect(zoho.organizationName, 'Sakshi Global Corp');
    });

    test('EmailMessage serialization with AI classification fields', () {
      final json = {
        'id': '31fed499-c819-4a78-ad5d-05ad562704ba',
        'file_name': 'WHC5X4X_GST_Invoice.pdf',
        'mime_type': 'application/pdf',
        'file_size': 65553,
        'email_subject': 'GST Tax Invoice - WHC5X4X',
        'email_sender': 'billing@vendor.com',
        'document_type': 'INVOICE',
        'financial_relevance': 'FINANCIAL',
        'classification_confidence': 0.99,
        'classification_reason': 'Valid tax invoice containing GSTIN, items, and tax split.',
        'status': 'STAGED',
      };

      final msg = EmailMessage.fromJson(json);
      expect(msg.id, '31fed499-c819-4a78-ad5d-05ad562704ba');
      expect(msg.fileName, 'WHC5X4X_GST_Invoice.pdf');
      expect(msg.fileSize, 65553);
      expect(msg.documentType, 'INVOICE');
      expect(msg.financialRelevance, 'FINANCIAL');
      expect(msg.classificationConfidence, 0.99);
      expect(msg.classificationReason, 'Valid tax invoice containing GSTIN, items, and tax split.');
      expect(msg.isProcessed, false);
    });

    test('Zoho master data models serialization', () {
      final acc = ZohoMasterAccount.fromJson({
        'id': '101',
        'account_name': 'Software Subscriptions',
        'account_code': 'EXP-101',
        'account_type': 'expense',
        'is_active': true,
      });
      expect(acc.name, 'Software Subscriptions');
      expect(acc.code, 'EXP-101');
      expect(acc.type, 'expense');

      final tax = ZohoMasterTax.fromJson({
        'id': '201',
        'tax_name': 'GST 18%',
        'tax_percentage': 18.0,
        'tax_type': 'tax',
      });
      expect(tax.name, 'GST 18%');
      expect(tax.percentage, 18.0);

      final vendor = ZohoMasterVendor.fromJson({
        'id': '301',
        'vendor_name': 'AWS India Services',
        'gstin': '29ABCDE1234F1Z5',
        'pan': 'ABCDE1234F',
        'approval_status': 'APPROVED',
      });
      expect(vendor.name, 'AWS India Services');
      expect(vendor.gstin, '29ABCDE1234F1Z5');
      expect(vendor.pan, 'ABCDE1234F');
    });

    test('Invoice displayStatus resolution tests', () {
      final exportedInv = Invoice.fromJson({
        'id': 'inv-1',
        'status': 'COMPLETED',
        'approval_status': 'APPROVED',
        'export_status': 'EXPORTED',
        'zoho_bill_id': '4163253000000046013',
      });
      expect(exportedInv.displayStatus, 'exported');

      final approvedInv = Invoice.fromJson({
        'id': 'inv-2',
        'status': 'COMPLETED',
        'approval_status': 'APPROVED',
        'export_status': 'NOT_EXPORTED',
      });
      expect(approvedInv.displayStatus, 'approved');

      final pendingInv = Invoice.fromJson({
        'id': 'inv-3',
        'status': 'COMPLETED',
        'approval_status': 'PENDING_REVIEW',
        'export_status': 'NOT_EXPORTED',
      });
      expect(pendingInv.displayStatus, 'pending');

      final stagedInv = Invoice.fromJson({
        'id': 'inv-4',
        'status': 'STAGED',
        'approval_status': 'PENDING_REVIEW',
        'export_status': 'NOT_EXPORTED',
      });
      expect(stagedInv.displayStatus, 'pending');

      final failedInv = Invoice.fromJson({
        'id': 'inv-5',
        'status': 'FAILED',
        'approval_status': 'PENDING_REVIEW',
        'export_status': 'FAILED',
      });
      expect(failedInv.displayStatus, 'failed');
    });

    test('HealthResponse and ServiceHealthDetail serialization', () {
      final json = {
        'status': 'healthy',
        'services': {
          'database': {
            'name': 'PostgreSQL DB',
            'status': 'connected',
            'latency_ms': 1.2,
            'status_code': 200,
            'message': 'Connected to PostgreSQL',
          },
          'zoho': {
            'name': 'Zoho Books API',
            'status': 'online',
            'latency_ms': 120.5,
            'status_code': 200,
            'message': 'Connected to organization',
          },
        },
      };

      final health = HealthResponse.fromJson(json);
      expect(health.status, 'healthy');
      expect(health.services.length, 2);
      expect(health.services['database']?.isHealthy, true);
      expect(health.services['database']?.latencyMs, 1.2);
      expect(health.services['zoho']?.name, 'Zoho Books API');
    });

    test('AuditLogEntry serialization', () {
      final json = {
        'id': 'audit-001',
        'action': 'OCR_EXTRACTION_COMPLETED',
        'user_email': 'system.ai@sakshifinance.com',
        'field_name': 'total_amount',
        'before_value': '0',
        'after_value': '59000.0',
        'reason': 'Automated Vision AI Pipeline extraction',
        'created_at': '2026-09-22T08:00:00Z',
      };

      final log = AuditLogEntry.fromJson(json);
      expect(log.id, 'audit-001');
      expect(log.action, 'OCR_EXTRACTION_COMPLETED');
      expect(log.userEmail, 'system.ai@sakshifinance.com');
      expect(log.fieldName, 'total_amount');
      expect(log.afterValue, '59000.0');
    });

    test('ZohoMasterDataSummary and ZohoOrganization serialization', () {
      final org = ZohoOrganization.fromJson({
        'organization_id': 'ORG_12345',
        'name': 'Sakshi India Operations',
        'currency_code': 'INR',
        'is_default_org': true,
      });
      expect(org.organizationId, 'ORG_12345');
      expect(org.name, 'Sakshi India Operations');
      expect(org.isDefault, true);

      final summary = ZohoMasterDataSummary.fromJson({
        'accounts_count': 142,
        'taxes_count': 12,
        'vendors_count': 38,
      });
      expect(summary.accountsCount, 142);
      expect(summary.taxesCount, 12);
      expect(summary.vendorsCount, 38);
    });

    test('Invoice accounting period and previous FY flag serialization', () {
      final inv = Invoice.fromJson({
        'id': 'inv-fy-01',
        'status': 'STAGED',
        'period_category': 'PREVIOUS_FY',
        'period_decision': 'PENDING_CONFIRMATION',
      });
      expect(inv.periodCategory, 'PREVIOUS_FY');
      expect(inv.periodDecision, 'PENDING_CONFIRMATION');
    });

    test('Invoice #108 Professional Fees line item with derived rate preserves data when changing GST %', () {
      final invoiceJson = {
        'id': 'inv-108',
        'status': 'PENDING_REVIEW',
        'current_vlm_output': {
          'invoice_number': '108',
          'invoice_date': '22-Sep-26',
          'vendor_name': 'GER & ASSOCIATES',
          'vendor_gstin': '29AAVFG4553H1ZT',
          'customer_name': 'Jukshio Technology Innovation Private Limited',
          'customer_gstin': '36AAECJ6056C1ZQ',
          'taxable_amount': 90000.0,
          'igst_amount': 16200.0,
          'total_amount': 106200.0,
          'line_items': [
            {
              'description': 'Professional Fees',
              'hsn_code': '9982',
              'quantity': 1.0,
              'unit_price': 0.0,
              'taxable_amount': 90000.0,
              'igst_rate': 18.0,
              'igst_amount': 16200.0,
              'total': 106200.0,
            }
          ]
        }
      };

      final invoice = Invoice.fromJson(invoiceJson);
      final item = invoice.extractedData!.lineItems.first;
      expect(item.taxableAmount, 90000.0);
      expect(item.unitPrice, 90000.0); // Derived from taxable_amount / quantity
      expect(item.total, 106200.0);

      // Simulate provider updating the line item rate
      final provider = InvoiceProvider();
      provider.setActiveInvoice(invoice);
      provider.updateLineItem(0, item..gstRate = 5.0);

      expect(provider.editableData!.lineItems.first.taxableAmount, 90000.0);
      expect(provider.editableData!.taxableAmount, 90000.0);
      expect(provider.editableData!.lineItems.first.total, 94500.0);
      expect(provider.editableData!.totalAmount, 94500.0);
    });

    test('InvoiceProvider interactive journal line editing, add, delete, and reset', () {
      final provider = InvoiceProvider();
      provider.setActiveInvoice(Invoice(
        id: 108,
        filename: 'invoice_108.pdf',
        status: 'PENDING_REVIEW',
        extractedData: ExtractedInvoiceData(
          taxableAmount: 100000.0,
          cgstAmount: 9000.0,
          sgstAmount: 9000.0,
          totalAmount: 118000.0,
          vendorName: 'Test Vendor',
        ),
      ));

      expect(provider.editableJournal, isNotNull);
      expect(provider.editableJournal!.lines.isNotEmpty, true);
      expect(provider.isJournalCustomized, false);

      // Edit a journal line
      provider.updateJournalLine(0, JournalLine(
        accountCode: 'EXP-CUSTOM',
        accountName: 'Custom Legal Expense',
        debit: 100000.0,
        credit: 0.0,
      ));

      expect(provider.isJournalCustomized, true);
      expect(provider.editableJournal!.lines.first.accountCode, 'EXP-CUSTOM');
      expect(provider.editableJournal!.lines.first.accountName, 'Custom Legal Expense');

      // Add a line
      final initialCount = provider.editableJournal!.lines.length;
      provider.addJournalLine();
      expect(provider.editableJournal!.lines.length, initialCount + 1);

      // Delete a line
      provider.removeJournalLine(provider.editableJournal!.lines.length - 1);
      expect(provider.editableJournal!.lines.length, initialCount);

      // Reset to auto
      provider.resetJournalToAuto();
      expect(provider.isJournalCustomized, false);
      expect(provider.editableJournal!.lines.first.accountCode, 'EXP-100');
    });

    test('Indian and Foreign invoice classification and separation tests', () {
      final indianJson = {
        'id': 201,
        'filename': 'tcs_consulting_inv.pdf',
        'status': 'EXTRACTED',
        'invoice_origin': 'INDIAN',
        'currency': 'INR',
        'extracted_data': {
          'vendor_name': 'Tata Consultancy Services Ltd',
          'vendor_gstin': '27AAACT2727Q1ZW',
          'total_amount': 150000.0,
        },
      };

      final foreignJson = {
        'id': 202,
        'filename': 'aws_cloud_service.pdf',
        'status': 'EXTRACTED',
        'invoice_origin': 'FOREIGN',
        'currency': 'USD',
        'extracted_data': {
          'vendor_name': 'Amazon Web Services, Inc.',
          'total_amount': 450.0,
        },
      };

      final indianInvoice = Invoice.fromJson(indianJson);
      final foreignInvoice = Invoice.fromJson(foreignJson);

      expect(indianInvoice.isIndian, true);
      expect(indianInvoice.isForeign, false);
      expect(indianInvoice.currency, 'INR');

      expect(foreignInvoice.isIndian, false);
      expect(foreignInvoice.isForeign, true);
      expect(foreignInvoice.currency, 'USD');

      // Email message origin tests
      final emailMsgIndian = EmailMessage.fromJson({
        'id': 'msg-1',
        'subject': 'Tax Invoice #1024',
        'sender': 'billing@vendor.in',
        'date': '2026-09-28',
        'invoice_origin': 'INDIAN',
        'currency': 'INR',
      });

      final emailMsgForeign = EmailMessage.fromJson({
        'id': 'msg-2',
        'subject': 'Subscription Invoice INV-US-99',
        'sender': 'invoicing@stripe.com',
        'date': '2026-09-28',
        'invoice_origin': 'FOREIGN',
        'currency': 'USD',
      });

      expect(emailMsgIndian.isIndian, true);
      expect(emailMsgIndian.isForeign, false);
      expect(emailMsgIndian.currency, 'INR');

      expect(emailMsgForeign.isIndian, false);
      expect(emailMsgForeign.isForeign, true);
      expect(emailMsgForeign.currency, 'USD');
    });

    test('AdminUser and AdminInvitation serialization', () {
      final userJson = {
        'id': 'u-12345',
        'email': 'admin@sakshifinance.com',
        'full_name': 'Super Admin',
        'role': 'ADMIN',
        'is_active': true,
        'must_change_password': true,
        'created_at': '2026-09-28T12:00:00Z',
      };

      final adminUser = AdminUser.fromJson(userJson);
      expect(adminUser.id, 'u-12345');
      expect(adminUser.email, 'admin@sakshifinance.com');
      expect(adminUser.role, 'ADMIN');
      expect(adminUser.isActive, true);
      expect(adminUser.mustChangePassword, true);

      final invJson = {
        'id': 'inv-67890',
        'email': 'newhire@sakshifinance.com',
        'role': 'FINANCE_USER',
        'status': 'OTP_VERIFICATION_PENDING',
        'expires_at': '2026-10-05T12:00:00Z',
      };

      final adminInv = AdminInvitation.fromJson(invJson);
      expect(adminInv.id, 'inv-67890');
      expect(adminInv.email, 'newhire@sakshifinance.com');
      expect(adminInv.role, 'FINANCE_USER');
      expect(adminInv.status, 'OTP_VERIFICATION_PENDING');
      expect(adminInv.expiresAt, isNotNull);
    });

    test('Foreign currency & FX fields serialization and backwards compatibility', () {
      // 1. Foreign Invoice with full FX metadata
      final foreignJson = {
        'id': 'inv-fx-001',
        'file_name': 'aws_cloud_inv.pdf',
        'status': 'PROCESSED',
        'invoice_origin': 'FOREIGN',
        'currency': 'USD',
        'original_currency': 'USD',
        'original_total_amount': 6400.0,
        'original_taxable_amount': 6400.0,
        'exchange_rate': 87.123456,
        'exchange_rate_date': '2026-09-28',
        'exchange_rate_source': 'EXCHANGE_RATE_API',
        'converted_total_inr': 557590.12,
        'converted_taxable_inr': 557590.12,
        'fx_rate_overridden': true,
        'fx_override_reason': 'Agreed treasury contract rate',
        'fx_original_rate': 86.95,
        'extracted_data': {
          'vendor_name': 'Amazon Web Services Inc',
          'total_amount': 6400.0,
          'currency': 'USD',
          'original_currency': 'USD',
          'original_total_amount': 6400.0,
          'exchange_rate': 87.123456,
          'exchange_rate_date': '2026-09-28',
          'converted_total_inr': 557590.12,
        },
      };

      final inv = Invoice.fromJson(foreignJson);
      expect(inv.isForeign, true);
      expect(inv.currency, 'USD');
      expect(inv.originalCurrency, 'USD');
      expect(inv.originalTotalAmount, 6400.0);
      expect(inv.exchangeRate, 87.123456);
      expect(inv.exchangeRateDate, '2026-09-28');
      expect(inv.convertedTotalInr, 557590.12);
      expect(inv.fxRateOverridden, true);
      expect(inv.fxOverrideReason, 'Agreed treasury contract rate');
      expect(inv.fxOriginalRate, 86.95);

      final ext = inv.extractedData!;
      expect(ext.originalCurrency, 'USD');
      expect(ext.originalTotalAmount, 6400.0);
      expect(ext.exchangeRate, 87.123456);
      expect(ext.convertedTotalInr, 557590.12);

      // 2. Legacy Domestic JSON without FX fields -> must safely default without crashing
      final legacyJson = {
        'id': 'inv-legacy-1',
        'file_name': 'domestic_bill.pdf',
        'status': 'PROCESSED',
        'total_amount': 15000.0,
      };

      final legacyInv = Invoice.fromJson(legacyJson);
      expect(legacyInv.isIndian, true);
      expect(legacyInv.currency, 'INR');
      expect(legacyInv.originalCurrency, 'INR');
      expect(legacyInv.exchangeRate, 1.0);
      expect(legacyInv.convertedTotalInr, isNull);
      expect(legacyInv.fxRateOverridden, false);
      expect(legacyInv.fxOverrideReason, isNull);
    });
  });
}

