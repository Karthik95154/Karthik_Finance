const Map<String, String> kGstStateMap = {
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
  '26': 'Dadra and Nagar Haveli and Daman and Diu',
  '27': 'Maharashtra',
  '29': 'Karnataka',
  '30': 'Goa',
  '31': 'Lakshadweep',
  '32': 'Kerala',
  '33': 'Tamil Nadu',
  '34': 'Puducherry',
  '35': 'Andaman and Nicobar Islands',
  '36': 'Telangana',
  '37': 'Andhra Pradesh',
  '38': 'Ladakh',
  '97': 'Other Territory',
};

class BankDetails {
  String? accountHolderName;
  String? accountNumber;
  String? ifscCode;
  String? bankName;
  String? branch;
  String? upiId;
  String? swiftBic;
  String? iban;
  String? rawText;

  BankDetails({
    this.accountHolderName,
    this.accountNumber,
    this.ifscCode,
    this.bankName,
    this.branch,
    this.upiId,
    this.swiftBic,
    this.iban,
    this.rawText,
  });

  bool get isNotEmpty =>
      (accountNumber != null && accountNumber!.isNotEmpty) ||
      (ifscCode != null && ifscCode!.isNotEmpty) ||
      (swiftBic != null && swiftBic!.isNotEmpty) ||
      (iban != null && iban!.isNotEmpty) ||
      (rawText != null && rawText!.isNotEmpty);

  String get summaryText {
    if (swiftBic != null && swiftBic!.isNotEmpty) {
      return 'SWIFT: $swiftBic ${iban != null && iban!.isNotEmpty ? "(IBAN: $iban)" : ""}';
    }
    if (accountNumber != null && accountNumber!.isNotEmpty) {
      return 'A/C: $accountNumber ${ifscCode != null ? "(IFSC: $ifscCode)" : ""}';
    }
    return rawText ?? 'Bank on file';
  }

  factory BankDetails.fromJson(Map<String, dynamic> json) {
    return BankDetails(
      accountHolderName: json['account_holder_name']?.toString() ??
          json['holder_name']?.toString() ??
          json['beneficiary_name']?.toString() ??
          json['account_name']?.toString() ??
          json['name']?.toString(),
      accountNumber: json['account_number']?.toString() ??
          json['acc_no']?.toString() ??
          json['account_no']?.toString() ??
          json['acc_num']?.toString() ??
          json['bank_account']?.toString(),
      ifscCode: json['ifsc_code']?.toString() ??
          json['ifsc']?.toString() ??
          json['ifsc_num']?.toString() ??
          json['bank_ifsc']?.toString(),
      bankName: json['bank_name']?.toString() ??
          json['bank']?.toString() ??
          json['bank_title']?.toString(),
      branch: json['branch']?.toString() ??
          json['branch_name']?.toString() ??
          json['branch_address']?.toString(),
      upiId: json['upi_id']?.toString() ??
          json['upi']?.toString() ??
          json['vpa']?.toString() ??
          json['upi_handle']?.toString(),
      swiftBic: json['swift_bic']?.toString() ??
          json['swift_code']?.toString() ??
          json['swift']?.toString() ??
          json['bic']?.toString(),
      iban: json['iban']?.toString() ??
          json['iban_number']?.toString(),
      rawText: json['raw_text']?.toString() ?? json['text']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'account_holder_name': accountHolderName,
      'account_number': accountNumber,
      'ifsc_code': ifscCode,
      'bank_name': bankName,
      'branch': branch,
      'upi_id': upiId,
      'swift_bic': swiftBic,
      'iban': iban,
      'raw_text': rawText,
    };
  }
}

class LineItem {
  int? lineIndex;
  String? description;
  String? hsnCode;
  double? quantity;
  String? unit;
  double? unitPrice;
  double? rate;
  double? discount;
  String? discountType;
  double? lineAmount;
  double? taxableAmount;
  double? gstRate;
  double? cgstRate;
  double? cgstAmount;
  double? sgstRate;
  double? sgstAmount;
  double? igstRate;
  double? igstAmount;
  double? cessRate;
  double? cessAmount;
  String? accountId;
  String? accountName;
  double? total;

  // Foreign currency audit fields
  double? originalUnitPrice;
  double? originalRate;
  double? originalTaxableAmount;
  double? originalLineAmount;
  double? originalTotal;
  String? originalCurrency;

  LineItem({
    this.lineIndex,
    this.description,
    this.hsnCode,
    this.quantity,
    this.unit,
    this.unitPrice,
    this.rate,
    this.discount,
    this.discountType,
    this.lineAmount,
    this.taxableAmount,
    this.gstRate,
    this.cgstRate,
    this.cgstAmount,
    this.sgstRate,
    this.sgstAmount,
    this.igstRate,
    this.igstAmount,
    this.cessRate,
    this.cessAmount,
    this.accountId,
    this.accountName,
    this.total,
    this.originalUnitPrice,
    this.originalRate,
    this.originalTaxableAmount,
    this.originalLineAmount,
    this.originalTotal,
    this.originalCurrency,
  });

  static double? _toDouble(dynamic val) {
    if (val == null) return null;
    if (val is num) return val.toDouble();
    if (val is String) {
      final cleaned = val.replaceAll(',', '').replaceAll('₹', '').replaceAll('\$', '').trim();
      return double.tryParse(cleaned);
    }
    return null;
  }

  factory LineItem.fromJson(Map<String, dynamic> json) {
    final rawFields = (json['raw_fields'] is Map<String, dynamic>)
        ? json['raw_fields'] as Map<String, dynamic>
        : null;

    final qty = _toDouble(json['quantity'] ??
            json['qty'] ??
            json['count'] ??
            json['units'] ??
            json['item_qty'] ??
            rawFields?['quantity']) ??
        1.0;

    var price = _toDouble(json['unit_price'] ??
            json['price'] ??
            json['rate'] ??
            json['unit_rate'] ??
            json['item_price'] ??
            json['item_rate'] ??
            rawFields?['unit_price']) ??
        0.0;

    final disc = _toDouble(json['discount'] ??
        json['item_discount'] ??
        json['disc'] ??
        rawFields?['discount']);

    double? taxable = _toDouble(json['taxable_amount'] ??
        json['taxable_value'] ??
        json['taxable'] ??
        json['base_amount'] ??
        json['line_amount'] ??
        json['amount'] ??
        rawFields?['taxable_amount']);

    if (taxable == null || taxable == 0.0) {
      if (qty > 0 && price > 0) {
        taxable = (qty * price) - (disc ?? 0.0);
      } else {
        taxable = _toDouble(json['line_amount'] ?? json['amount']) ?? 0.0;
      }
    }

    // Ensure price/rate and taxable amount are mathematically consistent:
    // If quantity is 1 (or salary/duty line where extracted rate was per-person/duty but taxable is the full line total),
    // price must equal taxable amount.
    if (taxable > 0) {
      if (qty == 1.0 || price == 0.0 || (qty > 0 && (qty * price - (disc ?? 0.0) - taxable).abs() > 0.05)) {
        price = (taxable + (disc ?? 0.0)) / (qty > 0 ? qty : 1.0);
      }
    }

    final cgstVal = _toDouble(json['cgst_amount'] ??
        json['cgst'] ??
        json['cgst_val'] ??
        rawFields?['cgst_amount']);
    final sgstVal = _toDouble(json['sgst_amount'] ??
        json['sgst'] ??
        json['sgst_val'] ??
        rawFields?['sgst_amount']);
    final igstVal = _toDouble(json['igst_amount'] ??
        json['igst'] ??
        json['igst_val'] ??
        rawFields?['igst_amount']);
    final cessVal = _toDouble(json['cess_amount'] ??
        json['cess'] ??
        json['cess_val'] ??
        rawFields?['cess_amount']);

    final cgstR = _toDouble(json['cgst_rate'] ?? json['cgst_pct'] ?? rawFields?['cgst_rate']);
    final sgstR = _toDouble(json['sgst_rate'] ?? json['sgst_pct'] ?? rawFields?['sgst_rate']);
    final igstR = _toDouble(json['igst_rate'] ?? json['igst_pct'] ?? rawFields?['igst_rate']);
    final cessR = _toDouble(json['cess_rate'] ?? json['cess_pct'] ?? rawFields?['cess_rate']);

    double? taxRate = _toDouble(json['gst_rate'] ??
        json['tax_rate'] ??
        json['gst_percentage'] ??
        json['gst_pct'] ??
        json['tax_pct'] ??
        json['rate_pct'] ??
        rawFields?['gst_rate']);

    if (taxRate == null) {
      if (cgstR != null && sgstR != null) {
        taxRate = cgstR + sgstR;
      } else if (igstR != null && igstR > 0) {
        taxRate = igstR;
      } else if (taxable > 0) {
        final totalTaxes = (cgstVal ?? 0.0) + (sgstVal ?? 0.0) + (igstVal ?? 0.0);
        if (totalTaxes > 0) {
          taxRate = ((totalTaxes / taxable) * 100).roundToDouble();
        }
      }
    }

    double? totalVal = _toDouble(json['total'] ??
        json['total_amount'] ??
        json['item_total'] ??
        json['line_total'] ??
        json['amount_with_tax'] ??
        json['gross_amount'] ??
        rawFields?['total']);

    if (totalVal == null || totalVal == 0.0) {
      final totalTaxes = (cgstVal ?? 0.0) + (sgstVal ?? 0.0) + (igstVal ?? 0.0) + (cessVal ?? 0.0);
      if (totalTaxes > 0) {
        totalVal = taxable + totalTaxes;
      } else if (taxRate != null && taxRate > 0) {
        totalVal = taxable * (1 + (taxRate / 100));
      } else {
        totalVal = taxable;
      }
    }

    final hsn = json['hsn_code']?.toString() ??
        json['hsn_sac_code']?.toString() ??
        json['hsn']?.toString() ??
        json['sac']?.toString() ??
        json['sac_code']?.toString() ??
        json['hsn_sac']?.toString() ??
        rawFields?['hsn_code']?.toString();

    final desc = json['description']?.toString() ??
        json['item_description']?.toString() ??
        json['item_name']?.toString() ??
        json['name']?.toString() ??
        json['product_name']?.toString() ??
        json['service_description']?.toString() ??
        json['particulars']?.toString() ??
        json['title']?.toString() ??
        rawFields?['description']?.toString();

    final origUnitPrice = _toDouble(json['original_unit_price'] ?? json['original_rate'] ?? rawFields?['original_unit_price']);
    final origTaxable = _toDouble(json['original_taxable_amount'] ?? rawFields?['original_taxable_amount']);
    final origLineAmount = _toDouble(json['original_line_amount'] ?? rawFields?['original_line_amount']);
    final origTotal = _toDouble(json['original_total'] ?? rawFields?['original_total']);
    final origCurr = json['original_currency']?.toString() ?? rawFields?['original_currency']?.toString();

    return LineItem(
      lineIndex: json['line_index'] is int
          ? json['line_index']
          : int.tryParse(json['line_index']?.toString() ??
              json['index']?.toString() ??
              json['s_no']?.toString() ??
              json['item_no']?.toString() ??
              ''),
      description: desc,
      hsnCode: hsn,
      quantity: qty,
      unit: json['unit']?.toString() ?? json['uom']?.toString(),
      unitPrice: price,
      rate: price,
      discount: disc,
      discountType: json['discount_type']?.toString(),
      lineAmount: _toDouble(json['line_amount'] ?? json['amount']),
      taxableAmount: taxable,
      gstRate: taxRate ?? 18.0,
      cgstRate: cgstR,
      cgstAmount: cgstVal,
      sgstRate: sgstR,
      sgstAmount: sgstVal,
      igstRate: igstR,
      igstAmount: igstVal,
      cessRate: cessR,
      cessAmount: cessVal,
      accountId: json['account_id']?.toString() ?? json['approved_account_id']?.toString(),
      accountName: json['account_name']?.toString() ?? json['account']?.toString() ?? json['approved_account_name']?.toString(),
      total: totalVal,
      originalUnitPrice: origUnitPrice,
      originalRate: origUnitPrice,
      originalTaxableAmount: origTaxable,
      originalLineAmount: origLineAmount,
      originalTotal: origTotal,
      originalCurrency: origCurr,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'line_index': lineIndex,
      'description': description,
      'hsn_code': hsnCode,
      'quantity': quantity,
      'unit': unit,
      'unit_price': unitPrice,
      'rate': rate,
      'discount': discount,
      'discount_type': discountType,
      'line_amount': lineAmount,
      'taxable_amount': taxableAmount,
      'gst_rate': gstRate,
      'cgst_rate': cgstRate,
      'cgst_amount': cgstAmount,
      'sgst_rate': sgstRate,
      'sgst_amount': sgstAmount,
      'igst_rate': igstRate,
      'igst_amount': igstAmount,
      'cess_rate': cessRate,
      'cess_amount': cessAmount,
      'account_id': accountId,
      'account_name': accountName,
      'total': total,
      'original_unit_price': originalUnitPrice,
      'original_rate': originalRate,
      'original_taxable_amount': originalTaxableAmount,
      'original_line_amount': originalLineAmount,
      'original_total': originalTotal,
      'original_currency': originalCurrency,
    };
  }
}

class ExtractedInvoiceData {
  String? schemaVersion;
  String? invoiceNumber;
  String? invoiceDate;
  String? dueDate;
  String? poNumber;
  String? placeOfSupply;

  String? vendorName;
  String? vendorAddress;
  String? vendorGstin;
  String? vendorPan;
  String? vendorPhone;
  String? vendorEmail;

  String? customerName;
  String? customerAddress;
  String? customerGstin;
  String? customerPan;

  BankDetails? bankDetails;
  List<LineItem> lineItems;

  double? subtotal;
  double? discountTotal;
  double? taxableAmount;
  double? taxTotal;
  double? cgstAmount;
  double? sgstAmount;
  double? igstAmount;
  double? cessAmount;
  double? shippingCharges;
  double? otherCharges;
  double? adjustment;
  double? roundOff;
  double? totalAmount;
  String? currency;
  String? paymentTerms;
  String? invoicePeriod;
  String? category;
  String? notes;

  // Foreign Currency & FX Fields (Step 1 Foundation)
  String? originalCurrency;
  double? originalTotalAmount;
  double? originalTaxableAmount;
  double? exchangeRate;
  String? exchangeRateDate;
  String? exchangeRateSource;
  double? convertedTotalInr;
  double? convertedTaxableInr;
  bool fxRateOverridden;
  String? fxOverrideReason;
  double? fxOriginalRate;
  String? vendorCountry;
  String? vendorTaxId;
  String? servicePeriod;
  String? serviceDescription;

  ExtractedInvoiceData({
    this.schemaVersion,
    this.invoiceNumber,
    this.invoiceDate,
    this.dueDate,
    this.poNumber,
    this.placeOfSupply,
    this.vendorName,
    this.vendorAddress,
    this.vendorGstin,
    this.vendorPan,
    this.vendorPhone,
    this.vendorEmail,
    this.customerName,
    this.customerAddress,
    this.customerGstin,
    this.customerPan,
    this.bankDetails,
    this.lineItems = const [],
    this.subtotal,
    this.discountTotal,
    this.taxableAmount,
    this.taxTotal,
    this.cgstAmount,
    this.sgstAmount,
    this.igstAmount,
    this.cessAmount,
    this.shippingCharges,
    this.otherCharges,
    this.adjustment,
    this.roundOff,
    this.totalAmount,
    this.currency = 'INR',
    this.paymentTerms,
    this.invoicePeriod,
    this.category,
    this.notes,
    this.originalCurrency = 'INR',
    this.originalTotalAmount,
    this.originalTaxableAmount,
    this.exchangeRate = 1.0,
    this.exchangeRateDate,
    this.exchangeRateSource,
    this.convertedTotalInr,
    this.convertedTaxableInr,
    this.fxRateOverridden = false,
    this.fxOverrideReason,
    this.fxOriginalRate,
    this.vendorCountry,
    this.vendorTaxId,
    this.servicePeriod,
    this.serviceDescription,
  });

  static double? _toDouble(dynamic val) {
    if (val == null) return null;
    if (val is num) return val.toDouble();
    if (val is String) {
      final cleaned = val.replaceAll(',', '').replaceAll('₹', '').replaceAll('\$', '').trim();
      return double.tryParse(cleaned);
    }
    return null;
  }

  static String? _derivePanFromGstin(String? gstin) {
    if (gstin == null) return null;
    final cleaned = gstin.replaceAll(RegExp(r'[^A-Za-z0-9]'), '').toUpperCase();
    if (cleaned.length >= 12) {
      final panSub = cleaned.substring(2, 12);
      if (RegExp(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$').hasMatch(panSub)) {
        return panSub;
      }
      return panSub;
    }
    return null;
  }

  static String? _derivePlaceOfSupply(String? pos, String? custGstin, String? vendGstin) {
    if (pos != null && pos.trim().isNotEmpty) return pos.trim();

    String? extractState(String? gstin) {
      if (gstin == null) return null;
      final cleaned = gstin.replaceAll(RegExp(r'[^A-Za-z0-9]'), '');
      if (cleaned.length >= 2) {
        final code = cleaned.substring(0, 2);
        if (kGstStateMap.containsKey(code)) {
          return '$code - ${kGstStateMap[code]}';
        }
      }
      return null;
    }

    final fromCust = extractState(custGstin);
    if (fromCust != null) return fromCust;

    final fromVend = extractState(vendGstin);
    if (fromVend != null) return fromVend;

    return null;
  }

  factory ExtractedInvoiceData.fromJson(Map<String, dynamic> rawJson) {
    final json = (rawJson['data'] is Map<String, dynamic>)
        ? rawJson['data'] as Map<String, dynamic>
        : rawJson;

    final invDetails = (json['invoice_details'] is Map<String, dynamic>)
        ? json['invoice_details'] as Map<String, dynamic>
        : null;

    final vDetails = (json['vendor_details'] is Map<String, dynamic>)
        ? json['vendor_details'] as Map<String, dynamic>
        : ((json['vendor'] is Map<String, dynamic>)
            ? json['vendor'] as Map<String, dynamic>
            : ((json['supplier'] is Map<String, dynamic>) ? json['supplier'] as Map<String, dynamic> : null));

    final cDetails = (json['customer_details'] is Map<String, dynamic>)
        ? json['customer_details'] as Map<String, dynamic>
        : ((json['customer'] is Map<String, dynamic>)
            ? json['customer'] as Map<String, dynamic>
            : ((json['buyer'] is Map<String, dynamic>) ? json['buyer'] as Map<String, dynamic> : null));

    final finDetails = (json['financial_details'] is Map<String, dynamic>)
        ? json['financial_details'] as Map<String, dynamic>
        : ((json['totals'] is Map<String, dynamic>)
            ? json['totals'] as Map<String, dynamic>
            : ((json['summary'] is Map<String, dynamic>) ? json['summary'] as Map<String, dynamic> : null));

    final taxesMap = (json['taxes'] is Map<String, dynamic>)
        ? json['taxes'] as Map<String, dynamic>
        : ((json['tax_breakup'] is Map<String, dynamic>)
            ? json['tax_breakup'] as Map<String, dynamic>
            : ((json['gst_result'] is Map<String, dynamic>) ? json['gst_result'] as Map<String, dynamic> : null));

    final rawFields = (json['raw_fields'] is Map<String, dynamic>)
        ? json['raw_fields'] as Map<String, dynamic>
        : null;

    List<LineItem> items = [];
    final rawItems = json['line_items'] ??
        json['items'] ??
        json['items_list'] ??
        json['invoice_items'] ??
        invDetails?['line_items'] ??
        rawJson['line_items'];

    if (rawItems is List) {
      items = rawItems
          .whereType<Map<String, dynamic>>()
          .map((item) => LineItem.fromJson(item))
          .toList();
    }

    BankDetails? bank;
    final rawBank = json['bank_details'] ??
        json['bank'] ??
        json['payment_details'] ??
        vDetails?['bank_details'] ??
        vDetails?['payment_details'] ??
        rawFields?['bank_details'] ??
        rawJson['bank_details'];

    if (rawBank is Map<String, dynamic>) {
      bank = BankDetails.fromJson(rawBank);
    } else {
      final accNo = json['account_number']?.toString() ??
          json['bank_account']?.toString() ??
          json['acc_no']?.toString() ??
          vDetails?['account_number']?.toString() ??
          rawFields?['account_number']?.toString();
      final ifsc = json['ifsc_code']?.toString() ??
          json['ifsc']?.toString() ??
          vDetails?['ifsc_code']?.toString() ??
          rawFields?['ifsc_code']?.toString();
      final bName = json['bank_name']?.toString() ??
          json['bank']?.toString() ??
          vDetails?['bank_name']?.toString() ??
          rawFields?['bank_name']?.toString();
      final upi = json['upi_id']?.toString() ??
          json['upi']?.toString() ??
          vDetails?['upi_id']?.toString() ??
          rawFields?['upi_id']?.toString();
      if (accNo != null || ifsc != null || bName != null || upi != null) {
        bank = BankDetails(
          accountHolderName: json['account_holder_name']?.toString() ??
              vDetails?['account_holder_name']?.toString() ??
              rawFields?['account_holder_name']?.toString(),
          accountNumber: accNo,
          ifscCode: ifsc,
          bankName: bName,
          branch: json['branch']?.toString() ?? vDetails?['branch']?.toString(),
          upiId: upi,
        );
      }
    }

    final vName = json['vendor_name']?.toString() ??
        json['supplier_name']?.toString() ??
        vDetails?['vendor_name']?.toString() ??
        vDetails?['name']?.toString() ??
        vDetails?['legal_name']?.toString() ??
        rawFields?['vendor_name']?.toString();

    final vGstin = json['vendor_gstin']?.toString() ??
        json['vendor_gst']?.toString() ??
        json['supplier_gstin']?.toString() ??
        json['supplier_gst']?.toString() ??
        json['gstin']?.toString() ??
        vDetails?['vendor_gstin']?.toString() ??
        vDetails?['gstin']?.toString() ??
        vDetails?['gst']?.toString() ??
        rawFields?['vendor_gstin']?.toString();

    String? vPan = json['vendor_pan']?.toString() ??
        json['supplier_pan']?.toString() ??
        json['pan']?.toString() ??
        vDetails?['vendor_pan']?.toString() ??
        vDetails?['pan']?.toString() ??
        rawFields?['vendor_pan']?.toString();

    if ((vPan == null || vPan.trim().isEmpty) && vGstin != null) {
      vPan = _derivePanFromGstin(vGstin);
    }

    final vAddress = json['vendor_address']?.toString() ??
        json['supplier_address']?.toString() ??
        vDetails?['vendor_address']?.toString() ??
        vDetails?['address']?.toString() ??
        rawFields?['vendor_address']?.toString();

    final vPhone = json['vendor_phone']?.toString() ??
        json['vendor_mobile']?.toString() ??
        vDetails?['vendor_phone']?.toString() ??
        vDetails?['phone']?.toString() ??
        vDetails?['mobile']?.toString() ??
        rawFields?['vendor_phone']?.toString();

    final vEmail = json['vendor_email']?.toString() ??
        vDetails?['vendor_email']?.toString() ??
        vDetails?['email']?.toString() ??
        rawFields?['vendor_email']?.toString();

    final cName = json['customer_name']?.toString() ??
        json['buyer_name']?.toString() ??
        json['client_name']?.toString() ??
        cDetails?['customer_name']?.toString() ??
        cDetails?['name']?.toString() ??
        cDetails?['buyer_name']?.toString() ??
        rawFields?['customer_name']?.toString();

    final cGstin = json['customer_gstin']?.toString() ??
        json['customer_gst']?.toString() ??
        json['buyer_gstin']?.toString() ??
        json['buyer_gst']?.toString() ??
        cDetails?['customer_gstin']?.toString() ??
        cDetails?['gstin']?.toString() ??
        cDetails?['gst']?.toString() ??
        rawFields?['customer_gstin']?.toString();

    String? cPan = json['customer_pan']?.toString() ??
        json['buyer_pan']?.toString() ??
        cDetails?['customer_pan']?.toString() ??
        cDetails?['pan']?.toString() ??
        rawFields?['customer_pan']?.toString();

    if ((cPan == null || cPan.trim().isEmpty) && cGstin != null) {
      cPan = _derivePanFromGstin(cGstin);
    }

    final cAddress = json['customer_address']?.toString() ??
        json['buyer_address']?.toString() ??
        cDetails?['customer_address']?.toString() ??
        cDetails?['address']?.toString() ??
        rawFields?['customer_address']?.toString();

    final invNum = json['invoice_number']?.toString() ??
        json['invoice_no']?.toString() ??
        json['inv_number']?.toString() ??
        json['inv_no']?.toString() ??
        json['bill_no']?.toString() ??
        json['bill_number']?.toString() ??
        invDetails?['invoice_number']?.toString() ??
        invDetails?['invoice_no']?.toString() ??
        rawFields?['invoice_number']?.toString();

    final invDate = json['invoice_date']?.toString() ??
        json['bill_date']?.toString() ??
        json['date']?.toString() ??
        json['invoice_dt']?.toString() ??
        json['inv_date']?.toString() ??
        invDetails?['invoice_date']?.toString() ??
        rawFields?['invoice_date']?.toString();

    final dueDate = json['due_date']?.toString() ??
        json['payment_due_date']?.toString() ??
        json['due_dt']?.toString() ??
        json['payment_due']?.toString() ??
        invDetails?['due_date']?.toString() ??
        rawFields?['due_date']?.toString();

    final poNum = json['po_number']?.toString() ??
        json['po_no']?.toString() ??
        json['purchase_order']?.toString() ??
        json['order_no']?.toString() ??
        json['po_reference']?.toString() ??
        invDetails?['po_number']?.toString() ??
        rawFields?['po_number']?.toString();

    final rawPos = json['place_of_supply']?.toString() ??
        json['pos']?.toString() ??
        json['supply_state']?.toString() ??
        json['place_of_delivery']?.toString() ??
        invDetails?['place_of_supply']?.toString() ??
        rawFields?['place_of_supply']?.toString();

    final pos = _derivePlaceOfSupply(rawPos, cGstin, vGstin);

    double? cgst = _toDouble(json['cgst_amount'] ??
        json['cgst_total'] ??
        json['cgst'] ??
        finDetails?['cgst_amount'] ??
        finDetails?['cgst_total'] ??
        taxesMap?['cgst'] ??
        taxesMap?['cgst_amount']);

    double? sgst = _toDouble(json['sgst_amount'] ??
        json['sgst_total'] ??
        json['sgst'] ??
        finDetails?['sgst_amount'] ??
        finDetails?['sgst_total'] ??
        taxesMap?['sgst'] ??
        taxesMap?['sgst_amount']);

    double? igst = _toDouble(json['igst_amount'] ??
        json['igst_total'] ??
        json['igst'] ??
        finDetails?['igst_amount'] ??
        finDetails?['igst_total'] ??
        taxesMap?['igst'] ??
        taxesMap?['igst_amount']);

    double? cess = _toDouble(json['cess_amount'] ??
        json['cess_total'] ??
        json['cess'] ??
        finDetails?['cess_amount'] ??
        finDetails?['cess_total'] ??
        taxesMap?['cess'] ??
        taxesMap?['cess_amount']);

    if ((cgst == null || cgst == 0) && items.isNotEmpty) {
      final sumCgst = items.fold<double>(0.0, (acc, it) => acc + (it.cgstAmount ?? 0.0));
      if (sumCgst > 0) cgst = sumCgst;
    }
    if ((sgst == null || sgst == 0) && items.isNotEmpty) {
      final sumSgst = items.fold<double>(0.0, (acc, it) => acc + (it.sgstAmount ?? 0.0));
      if (sumSgst > 0) sgst = sumSgst;
    }
    if ((igst == null || igst == 0) && items.isNotEmpty) {
      final sumIgst = items.fold<double>(0.0, (acc, it) => acc + (it.igstAmount ?? 0.0));
      if (sumIgst > 0) igst = sumIgst;
    }
    if ((cess == null || cess == 0) && items.isNotEmpty) {
      final sumCess = items.fold<double>(0.0, (acc, it) => acc + (it.cessAmount ?? 0.0));
      if (sumCess > 0) cess = sumCess;
    }

    double? sub = _toDouble(json['subtotal'] ??
        json['taxable_amount'] ??
        json['taxable_value'] ??
        json['base_amount'] ??
        finDetails?['subtotal'] ??
        finDetails?['taxable_amount'] ??
        taxesMap?['taxable_amount']);

    if ((sub == null || sub == 0.0) && items.isNotEmpty) {
      final sumSub = items.fold<double>(0.0, (acc, it) => acc + (it.taxableAmount ?? 0.0));
      if (sumSub > 0) sub = sumSub;
    }

    final disc = _toDouble(json['discount_total'] ??
        json['discount'] ??
        json['total_discount'] ??
        finDetails?['discount_total'] ??
        finDetails?['discount']);

    final roundOff = _toDouble(json['round_off'] ??
        json['roundoff'] ??
        finDetails?['round_off'] ??
        finDetails?['roundoff']);

    final taxTot = _toDouble(json['tax_total'] ??
        json['total_tax'] ??
        finDetails?['tax_total'] ??
        taxesMap?['total_tax'] ??
        ((cgst ?? 0.0) + (sgst ?? 0.0) + (igst ?? 0.0) + (cess ?? 0.0)));

    double? total = _toDouble(json['total_amount'] ??
        json['grand_total'] ??
        json['total'] ??
        json['invoice_amount'] ??
        finDetails?['total_amount'] ??
        finDetails?['grand_total'] ??
        finDetails?['total']);

    if ((total == null || total == 0.0) && items.isNotEmpty) {
      final sumTotal = items.fold<double>(0.0, (acc, it) => acc + (it.total ?? 0.0));
      if (sumTotal > 0) {
        total = sumTotal;
      } else if (sub != null && sub > 0) {
        total = sub + (taxTot ?? 0.0) + (roundOff ?? 0.0);
      }
    } else if (total == null && sub != null) {
      total = sub + (taxTot ?? 0.0) + (roundOff ?? 0.0);
    }

    return ExtractedInvoiceData(
      schemaVersion: json['schema_version']?.toString() ?? rawJson['schema_version']?.toString(),
      invoiceNumber: invNum,
      invoiceDate: invDate,
      dueDate: dueDate,
      poNumber: poNum,
      placeOfSupply: pos,
      vendorName: vName,
      vendorAddress: vAddress,
      vendorGstin: vGstin,
      vendorPan: vPan,
      vendorPhone: vPhone,
      vendorEmail: vEmail,
      customerName: cName,
      customerAddress: cAddress,
      customerGstin: cGstin,
      customerPan: cPan,
      bankDetails: bank,
      lineItems: items,
      subtotal: sub,
      discountTotal: disc,
      taxableAmount: sub,
      taxTotal: taxTot,
      cgstAmount: cgst,
      sgstAmount: sgst,
      igstAmount: igst,
      cessAmount: cess,
      shippingCharges: _toDouble(json['shipping_charges'] ??
          json['shipping_charge'] ??
          json['shipping'] ??
          json['freight'] ??
          finDetails?['shipping_charges'] ??
          finDetails?['shipping'] ??
          finDetails?['freight']),
      otherCharges: _toDouble(json['other_charges'] ??
          json['other_charge'] ??
          json['charges'] ??
          finDetails?['other_charges'] ??
          finDetails?['charges']),
      adjustment: _toDouble(json['adjustment'] ??
          json['adjustments'] ??
          finDetails?['adjustment'] ??
          finDetails?['adjustments']),
      roundOff: roundOff,
      totalAmount: total,
      currency: json['currency']?.toString() ?? invDetails?['currency']?.toString() ?? 'INR',
      paymentTerms: json['payment_terms']?.toString() ??
          json['terms']?.toString() ??
          json['payment_term']?.toString() ??
          invDetails?['payment_terms']?.toString() ??
          rawFields?['payment_terms']?.toString(),
      invoicePeriod: json['invoice_period']?.toString() ??
          json['period']?.toString() ??
          json['billing_period']?.toString() ??
          invDetails?['invoice_period']?.toString() ??
          rawFields?['invoice_period']?.toString(),
      category: json['category']?.toString() ??
          json['service_category']?.toString() ??
          invDetails?['category']?.toString() ??
          rawFields?['category']?.toString(),
      notes: json['notes']?.toString() ?? json['remarks']?.toString() ?? invDetails?['notes']?.toString(),
      originalCurrency: json['original_currency']?.toString() ??
          json['currency']?.toString() ??
          invDetails?['original_currency']?.toString() ??
          invDetails?['currency']?.toString() ??
          'INR',
      originalTotalAmount: _toDouble(json['original_total_amount'] ??
          invDetails?['original_total_amount'] ??
          finDetails?['original_total_amount']),
      originalTaxableAmount: _toDouble(json['original_taxable_amount'] ??
          invDetails?['original_taxable_amount'] ??
          finDetails?['original_taxable_amount']),
      exchangeRate: _toDouble(json['exchange_rate'] ??
          invDetails?['exchange_rate'] ??
          finDetails?['exchange_rate']) ??
          1.0,
      exchangeRateDate: json['exchange_rate_date']?.toString() ??
          invDetails?['exchange_rate_date']?.toString(),
      exchangeRateSource: json['exchange_rate_source']?.toString() ??
          invDetails?['exchange_rate_source']?.toString(),
      convertedTotalInr: _toDouble(json['converted_total_inr'] ??
          invDetails?['converted_total_inr'] ??
          finDetails?['converted_total_inr']),
      convertedTaxableInr: _toDouble(json['converted_taxable_inr'] ??
          invDetails?['converted_taxable_inr'] ??
          finDetails?['converted_taxable_inr']),
      fxRateOverridden: json['fx_rate_overridden'] == true ||
          invDetails?['fx_rate_overridden'] == true,
      fxOverrideReason: json['fx_override_reason']?.toString() ??
          invDetails?['fx_override_reason']?.toString(),
      fxOriginalRate: _toDouble(json['fx_original_rate'] ??
          invDetails?['fx_original_rate'] ??
          finDetails?['fx_original_rate']),
      vendorCountry: json['vendor_country']?.toString() ??
          json['country']?.toString() ??
          invDetails?['vendor_country']?.toString(),
      vendorTaxId: json['vendor_tax_id']?.toString() ??
          json['tax_id']?.toString() ??
          invDetails?['vendor_tax_id']?.toString(),
      servicePeriod: json['service_period']?.toString() ??
          json['billing_period']?.toString() ??
          invDetails?['service_period']?.toString(),
      serviceDescription: json['service_description']?.toString() ??
          invDetails?['service_description']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'schema_version': schemaVersion,
      'invoice_number': invoiceNumber,
      'invoice_date': invoiceDate,
      'due_date': dueDate,
      'po_number': poNumber,
      'place_of_supply': placeOfSupply,
      'vendor_name': vendorName,
      'vendor_address': vendorAddress,
      'vendor_gstin': vendorGstin,
      'vendor_pan': vendorPan,
      'vendor_phone': vendorPhone,
      'vendor_email': vendorEmail,
      'customer_name': customerName,
      'customer_address': customerAddress,
      'customer_gstin': customerGstin,
      'customer_pan': customerPan,
      'bank_details': bankDetails?.toJson(),
      'line_items': lineItems.map((e) => e.toJson()).toList(),
      'subtotal': subtotal,
      'discount_total': discountTotal,
      'taxable_amount': taxableAmount,
      'tax_total': taxTotal,
      'cgst_amount': cgstAmount,
      'sgst_amount': sgstAmount,
      'igst_amount': igstAmount,
      'cess_amount': cessAmount,
      'shipping_charges': shippingCharges,
      'other_charges': otherCharges,
      'adjustment': adjustment,
      'round_off': roundOff,
      'total_amount': totalAmount,
      'currency': currency,
      'payment_terms': paymentTerms,
      'invoice_period': invoicePeriod,
      'category': category,
      'notes': notes,
      'original_currency': originalCurrency,
      'original_total_amount': originalTotalAmount,
      'original_taxable_amount': originalTaxableAmount,
      'exchange_rate': exchangeRate,
      'exchange_rate_date': exchangeRateDate,
      'exchange_rate_source': exchangeRateSource,
      'converted_total_inr': convertedTotalInr,
      'converted_taxable_inr': convertedTaxableInr,
      'fx_rate_overridden': fxRateOverridden,
      'fx_override_reason': fxOverrideReason,
      'fx_original_rate': fxOriginalRate,
      'vendor_country': vendorCountry,
      'vendor_tax_id': vendorTaxId,
      'service_period': servicePeriod,
      'service_description': serviceDescription,
    };
  }
}

// ---------------------------------------------------------------------------
// Statutory TDS Models with YTD Threshold Logic
// ---------------------------------------------------------------------------
class TdsResult {
  bool? applicable;
  bool? tdsApplicable;
  String? tdsType;
  String? tdsSection;
  String? natureOfPayment;
  String? tdsProvision;
  double? tdsRate;
  double? statutoryRate;
  String? rateSource;
  double? tdsBaseAmount;
  String? baseSource;
  double? extractedTdsAmount;
  double? calculatedTdsAmount;
  double? proposedTdsAmount;
  double? tdsAmount;
  String? calculation;
  double? confidence;
  bool? needsReview;
  String? reason;
  String? tdsReasoning;
  bool? isApproved;
  String? approvalStatus;
  String? approvedBy;
  DateTime? approvedAt;
  bool? isRcm;
  // Threshold & YTD properties
  double? previousYtd;
  double? currentInvoiceAmount;
  double? projectedYtd;
  double? ytdAmount;
  double? thresholdLimit;
  bool? thresholdExceeded;
  bool? panValid;
  String? panStatus;
  bool? isZohoYtd;

  TdsResult({
    this.applicable,
    this.tdsApplicable,
    this.tdsType,
    this.tdsSection,
    this.natureOfPayment,
    this.tdsProvision,
    this.tdsRate,
    this.statutoryRate,
    this.rateSource,
    this.tdsBaseAmount,
    this.baseSource,
    this.extractedTdsAmount,
    this.calculatedTdsAmount,
    this.proposedTdsAmount,
    this.tdsAmount,
    this.calculation,
    this.confidence,
    this.needsReview,
    this.reason,
    this.tdsReasoning,
    this.isApproved,
    this.approvalStatus,
    this.approvedBy,
    this.approvedAt,
    this.isRcm,
    this.previousYtd,
    this.currentInvoiceAmount,
    this.projectedYtd,
    this.ytdAmount,
    this.thresholdLimit,
    this.thresholdExceeded,
    this.panValid,
    this.panStatus,
    this.isZohoYtd,
  });

  String? get section => tdsSection;
  double? get rate => tdsRate;

  static double? _toDouble(dynamic val) {
    if (val == null) return null;
    if (val is num) return val.toDouble();
    if (val is String) {
      final cleaned = val.replaceAll(',', '').replaceAll('₹', '').replaceAll('\$', '').trim();
      return double.tryParse(cleaned);
    }
    return null;
  }

  static bool? _toBool(dynamic val) {
    if (val == null) return null;
    if (val is bool) return val;
    final str = val.toString().trim().toLowerCase();
    return str == 'true' || str == 'yes' || str == '1' || str == 'applicable';
  }

  factory TdsResult.fromJson(Map<String, dynamic> json) {
    final app = _toBool(json['applicable'] ??
        json['tds_applicable'] ??
        json['is_applicable'] ??
        json['is_tds_applicable'] ??
        json['status']);

    final sec = json['tds_section']?.toString() ??
        json['legacy_provision_reference']?.toString() ??
        json['approved_tds_section']?.toString() ??
        json['section']?.toString() ??
        json['provision']?.toString() ??
        json['tds_provision']?.toString() ??
        json['section_code']?.toString() ??
        json['tds_rule']?.toString();

    final rate = _toDouble(json['tds_rate'] ??
        json['rate'] ??
        json['approved_tds_rate'] ??
        json['rate_percentage'] ??
        json['tds_percentage']);

    final statRate = _toDouble(json['statutory_rate'] ?? json['statutory_tds_rate']);

    final base = _toDouble(json['tds_base_amount'] ??
        json['base_amount'] ??
        json['taxable_amount'] ??
        json['tds_taxable_amount']);

    final calcAmt = _toDouble(json['calculated_tds_amount'] ?? json['proposed_tds_amount']);
    final extAmt = _toDouble(json['extracted_tds_amount']);
    final amt = _toDouble(json['tds_amount'] ?? json['amount'] ?? calcAmt ?? extAmt);

    final prevYtd = _toDouble(json['previous_ytd'] ??
        json['vendor_previous_ytd'] ??
        json['zoho_previous_ytd'] ??
        json['zoho_ytd'] ??
        json['ytd_amount'] ??
        json['ytd_pre_tax_subtotal'] ??
        json['vendor_ytd_amount']);
    final curAmt = _toDouble(json['current_invoice_amount'] ?? json['current_amount'] ?? base);
    final projYtd = _toDouble(json['projected_ytd'] ?? json['total_projected_ytd'] ?? (prevYtd != null && curAmt != null ? prevYtd + curAmt : null));
    final ytd = prevYtd ?? projYtd;
    final thresh = _toDouble(json['threshold_limit'] ?? json['threshold_amount'] ?? json['section_threshold'] ?? json['threshold']);

    return TdsResult(
      applicable: app ?? (sec != null && sec.isNotEmpty && (amt != null && amt > 0)),
      tdsApplicable: app,
      tdsType: json['tds_type']?.toString(),
      tdsSection: sec,
      natureOfPayment: json['nature_of_payment']?.toString() ??
          json['description']?.toString() ??
          json['payment_nature']?.toString(),
      tdsProvision: json['tds_provision']?.toString() ?? sec,
      tdsRate: rate,
      statutoryRate: statRate ?? rate,
      rateSource: json['rate_source']?.toString(),
      tdsBaseAmount: base,
      baseSource: json['base_source']?.toString(),
      extractedTdsAmount: extAmt,
      calculatedTdsAmount: calcAmt,
      proposedTdsAmount: calcAmt,
      tdsAmount: amt,
      calculation: json['calculation']?.toString() ?? json['formula']?.toString(),
      confidence: _toDouble(json['confidence'] ?? json['confidence_score']),
      needsReview: _toBool(json['needs_review'] ?? json['requires_review']),
      reason: json['reason']?.toString() ??
          json['rationale']?.toString() ??
          json['justification']?.toString(),
      tdsReasoning: json['tds_reasoning']?.toString() ?? json['reasoning']?.toString(),
      isApproved: _toBool(json['is_approved'] ?? (json['approval_status'] == 'APPROVED')),
      approvalStatus: json['approval_status']?.toString(),
      approvedBy: json['approved_by']?.toString(),
      approvedAt: json['approved_at'] != null ? DateTime.tryParse(json['approved_at'].toString()) : null,
      isRcm: _toBool(json['is_rcm'] ?? json['rcm_applicable'] ?? json['rcm']) ?? false,
      previousYtd: prevYtd,
      currentInvoiceAmount: curAmt,
      projectedYtd: projYtd,
      ytdAmount: ytd,
      thresholdLimit: thresh,
      thresholdExceeded: _toBool(json['threshold_exceeded'] ?? (projYtd != null && thresh != null && projYtd >= thresh) ?? (ytd != null && thresh != null && ytd >= thresh)),
      panValid: _toBool(json['pan_valid'] ?? json['is_pan_valid'] ?? (json['pan_status'] == 'VALID')),
      panStatus: json['pan_status']?.toString() ?? (json['vendor_pan'] != null ? 'VALID' : 'MISSING'),
      isZohoYtd: _toBool(json['is_zoho_ytd'] ?? (prevYtd != null && prevYtd > 0)),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'applicable': applicable,
      'tds_applicable': tdsApplicable,
      'tds_type': tdsType,
      'tds_section': tdsSection,
      'nature_of_payment': natureOfPayment,
      'tds_provision': tdsProvision,
      'tds_rate': tdsRate,
      'statutory_rate': statutoryRate,
      'rate_source': rateSource,
      'tds_base_amount': tdsBaseAmount,
      'base_source': baseSource,
      'extracted_tds_amount': extractedTdsAmount,
      'calculated_tds_amount': calculatedTdsAmount,
      'proposed_tds_amount': proposedTdsAmount,
      'tds_amount': tdsAmount,
      'calculation': calculation,
      'confidence': confidence,
      'needs_review': needsReview,
      'reason': reason,
      'tds_reasoning': tdsReasoning,
      'is_approved': isApproved,
      'approval_status': approvalStatus,
      'approved_by': approvedBy,
      'approved_at': approvedAt?.toIso8601String(),
      'is_rcm': isRcm,
      'previous_ytd': previousYtd,
      'current_invoice_amount': currentInvoiceAmount,
      'projected_ytd': projectedYtd,
      'ytd_amount': ytdAmount,
      'threshold_limit': thresholdLimit,
      'threshold_exceeded': thresholdExceeded,
      'pan_valid': panValid,
      'pan_status': panStatus,
      'is_zoho_ytd': isZohoYtd,
    };
  }
}

// ---------------------------------------------------------------------------
// ITC (Input Tax Credit) Section 16 & 17(5) Models
// ---------------------------------------------------------------------------
class ItcLineItemBreakdown {
  final int lineIndex;
  final String description;
  final String? accountName;
  final String? hsnCode;
  final double? taxAmount;
  final String itcStatus; // ELIGIBLE, PARTIALLY_ELIGIBLE, INELIGIBLE, REVIEW_REQUIRED
  final double eligibleAmount;
  final double ineligibleAmount;
  final double? blockedAmount;
  final double? reversalAmount;
  final double? reviewAmount;
  final double? netItcAvailable;
  final String reason;
  final String ruleReference;
  final List<String> evidenceUsed;

  ItcLineItemBreakdown({
    required this.lineIndex,
    required this.description,
    this.accountName,
    this.hsnCode,
    this.taxAmount,
    required this.itcStatus,
    this.eligibleAmount = 0.0,
    this.ineligibleAmount = 0.0,
    this.blockedAmount,
    this.reversalAmount,
    this.reviewAmount,
    this.netItcAvailable,
    this.reason = '',
    this.ruleReference = '',
    this.evidenceUsed = const [],
  });

  static double _toDouble(dynamic val) {
    if (val == null) return 0.0;
    if (val is num) return val.toDouble();
    if (val is String) {
      final cleaned = val.replaceAll(',', '').replaceAll('₹', '').replaceAll('\$', '').trim();
      return double.tryParse(cleaned) ?? 0.0;
    }
    return 0.0;
  }

  factory ItcLineItemBreakdown.fromJson(Map<String, dynamic> json) {
    return ItcLineItemBreakdown(
      lineIndex: json['line_index'] is int ? json['line_index'] : (int.tryParse(json['line_index']?.toString() ?? '0') ?? 0),
      description: json['description']?.toString() ?? 'Line Item',
      accountName: json['account_name']?.toString(),
      hsnCode: json['hsn_code']?.toString(),
      taxAmount: _toDouble(json['tax_amount']),
      itcStatus: json['itc_status']?.toString() ?? json['status']?.toString() ?? 'ELIGIBLE',
      eligibleAmount: _toDouble(json['eligible_amount']),
      ineligibleAmount: _toDouble(json['ineligible_amount']),
      blockedAmount: _toDouble(json['blocked_amount']),
      reversalAmount: _toDouble(json['reversal_amount']),
      reviewAmount: _toDouble(json['review_amount']),
      netItcAvailable: _toDouble(json['net_itc_available']),
      reason: json['reason']?.toString() ?? '',
      ruleReference: json['rule_reference']?.toString() ?? '',
      evidenceUsed: (json['evidence_used'] as List?)?.map((e) => e.toString()).toList() ?? [],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'line_index': lineIndex,
      'description': description,
      'account_name': accountName,
      'hsn_code': hsnCode,
      'tax_amount': taxAmount,
      'itc_status': itcStatus,
      'eligible_amount': eligibleAmount,
      'ineligible_amount': ineligibleAmount,
      'blocked_amount': blockedAmount,
      'reversal_amount': reversalAmount,
      'review_amount': reviewAmount,
      'net_itc_available': netItcAvailable,
      'reason': reason,
      'rule_reference': ruleReference,
      'evidence_used': evidenceUsed,
    };
  }
}

class ItcResult {
  String status; // ELIGIBLE, PARTIALLY_ELIGIBLE, INELIGIBLE, REVIEW_REQUIRED
  double eligibleAmount;
  double ineligibleAmount;
  double? eligibleItc;
  double? blockedItc;
  double? reversalItc;
  double? reviewAmount;
  double? netItcAvailable;
  double totalTaxAmount;
  bool isReverseCharge;
  String? supplyType;
  String? reason;
  String? ruleReference;
  List<String> warnings;
  List<String> errors;
  List<ItcLineItemBreakdown> lineItemBreakdown;

  ItcResult({
    required this.status,
    this.eligibleAmount = 0.0,
    this.ineligibleAmount = 0.0,
    this.eligibleItc,
    this.blockedItc,
    this.reversalItc,
    this.reviewAmount,
    this.netItcAvailable,
    this.totalTaxAmount = 0.0,
    this.isReverseCharge = false,
    this.supplyType,
    this.reason,
    this.ruleReference,
    this.warnings = const [],
    this.errors = const [],
    this.lineItemBreakdown = const [],
  });

  static double _toDouble(dynamic val) {
    if (val == null) return 0.0;
    if (val is num) return val.toDouble();
    if (val is String) {
      final cleaned = val.replaceAll(',', '').replaceAll('₹', '').replaceAll('\$', '').trim();
      return double.tryParse(cleaned) ?? 0.0;
    }
    return 0.0;
  }

  factory ItcResult.fromJson(Map<String, dynamic> json) {
    final rawLines = json['line_item_breakdown'] as List?;
    final lines = rawLines != null
        ? rawLines.whereType<Map<String, dynamic>>().map((l) => ItcLineItemBreakdown.fromJson(l)).toList()
        : <ItcLineItemBreakdown>[];

    return ItcResult(
      status: json['status']?.toString() ?? 'ELIGIBLE',
      eligibleAmount: _toDouble(json['eligible_amount'] ?? json['eligible_itc']),
      ineligibleAmount: _toDouble(json['ineligible_amount'] ?? json['blocked_itc']),
      eligibleItc: _toDouble(json['eligible_itc']),
      blockedItc: _toDouble(json['blocked_itc']),
      reversalItc: _toDouble(json['reversal_itc']),
      reviewAmount: _toDouble(json['review_amount']),
      netItcAvailable: _toDouble(json['net_itc_available'] ?? json['eligible_amount']),
      totalTaxAmount: _toDouble(json['total_tax_amount'] ?? json['tax_total']),
      isReverseCharge: json['is_reverse_charge'] == true || json['is_rcm'] == true,
      supplyType: json['supply_type']?.toString(),
      reason: json['reason']?.toString(),
      ruleReference: json['rule_reference']?.toString(),
      warnings: (json['warnings'] as List?)?.map((w) => w.toString()).toList() ?? [],
      errors: (json['errors'] as List?)?.map((e) => e.toString()).toList() ?? [],
      lineItemBreakdown: lines,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'status': status,
      'eligible_amount': eligibleAmount,
      'ineligible_amount': ineligibleAmount,
      'eligible_itc': eligibleItc,
      'blocked_itc': blockedItc,
      'reversal_itc': reversalItc,
      'review_amount': reviewAmount,
      'net_itc_available': netItcAvailable,
      'total_tax_amount': totalTaxAmount,
      'is_reverse_charge': isReverseCharge,
      'supply_type': supplyType,
      'reason': reason,
      'rule_reference': ruleReference,
      'warnings': warnings,
      'errors': errors,
      'line_item_breakdown': lineItemBreakdown.map((e) => e.toJson()).toList(),
    };
  }
}

// ---------------------------------------------------------------------------
// GST Engine & Supply Validation Models
// ---------------------------------------------------------------------------
class GstLineValidation {
  final int lineIndex;
  final String description;
  final double? taxableAmount;
  final double? extractedCgst;
  final double? extractedSgst;
  final double? extractedIgst;
  final double? calculatedCgst;
  final double? calculatedSgst;
  final double? calculatedIgst;

  GstLineValidation({
    required this.lineIndex,
    required this.description,
    this.taxableAmount,
    this.extractedCgst,
    this.extractedSgst,
    this.extractedIgst,
    this.calculatedCgst,
    this.calculatedSgst,
    this.calculatedIgst,
  });

  factory GstLineValidation.fromJson(Map<String, dynamic> json) {
    double? _num(dynamic v) => v is num ? v.toDouble() : double.tryParse(v?.toString() ?? '');
    return GstLineValidation(
      lineIndex: json['line_index'] is int ? json['line_index'] : (int.tryParse(json['line_index']?.toString() ?? '0') ?? 0),
      description: json['description']?.toString() ?? 'Line',
      taxableAmount: _num(json['taxable_amount']),
      extractedCgst: _num(json['extracted_cgst']),
      extractedSgst: _num(json['extracted_sgst']),
      extractedIgst: _num(json['extracted_igst']),
      calculatedCgst: _num(json['calculated_cgst']),
      calculatedSgst: _num(json['calculated_sgst']),
      calculatedIgst: _num(json['calculated_igst']),
    );
  }
}

class GstResult {
  final String? supplierStateCode;
  final String? supplierStateName;
  final String? buyerStateCode;
  final String? buyerStateName;
  final String? placeOfSupplyStateCode;
  final String? placeOfSupplyStateName;
  final String? placeOfSupplySource;
  final String supplyType; // INTRA_STATE, INTER_STATE, REVIEW_REQUIRED
  final bool isReverseCharge;
  final String validationStatus; // PASSED, GST_MISMATCH, REVIEW_REQUIRED
  final double? extractedCgst;
  final double? extractedSgst;
  final double? extractedIgst;
  final double? extractedTaxTotal;
  final double? calculatedCgst;
  final double? calculatedSgst;
  final double? calculatedIgst;
  final double? calculatedGstTotal;
  final List<String> errors;
  final List<String> warnings;
  final List<GstLineValidation> lineValidations;

  GstResult({
    this.supplierStateCode,
    this.supplierStateName,
    this.buyerStateCode,
    this.buyerStateName,
    this.placeOfSupplyStateCode,
    this.placeOfSupplyStateName,
    this.placeOfSupplySource,
    this.supplyType = 'INTRA_STATE',
    this.isReverseCharge = false,
    this.validationStatus = 'PASSED',
    this.extractedCgst,
    this.extractedSgst,
    this.extractedIgst,
    this.extractedTaxTotal,
    this.calculatedCgst,
    this.calculatedSgst,
    this.calculatedIgst,
    this.calculatedGstTotal,
    this.errors = const [],
    this.warnings = const [],
    this.lineValidations = const [],
  });

  factory GstResult.fromJson(Map<String, dynamic> json) {
    double? _num(dynamic v) => v is num ? v.toDouble() : double.tryParse(v?.toString() ?? '');
    final ext = json['extracted'] as Map<String, dynamic>?;
    final calc = json['calculated'] as Map<String, dynamic>?;

    final lv = (json['line_validations'] as List?)
            ?.whereType<Map<String, dynamic>>()
            .map((e) => GstLineValidation.fromJson(e))
            .toList() ??
        [];

    return GstResult(
      supplierStateCode: json['supplier_state_code']?.toString(),
      supplierStateName: json['supplier_state_name']?.toString(),
      buyerStateCode: json['buyer_state_code']?.toString(),
      buyerStateName: json['buyer_state_name']?.toString(),
      placeOfSupplyStateCode: json['place_of_supply_state_code']?.toString(),
      placeOfSupplyStateName: json['place_of_supply_state_name']?.toString(),
      placeOfSupplySource: json['place_of_supply_source']?.toString(),
      supplyType: json['supply_type']?.toString() ?? 'INTRA_STATE',
      isReverseCharge: json['is_reverse_charge'] == true || json['is_rcm'] == true,
      validationStatus: json['validation_status']?.toString() ?? 'PASSED',
      extractedCgst: _num(ext?['cgst_amount'] ?? json['extracted_cgst']),
      extractedSgst: _num(ext?['sgst_amount'] ?? json['extracted_sgst']),
      extractedIgst: _num(ext?['igst_amount'] ?? json['extracted_igst']),
      extractedTaxTotal: _num(ext?['tax_total'] ?? json['extracted_tax_total']),
      calculatedCgst: _num(calc?['cgst_amount'] ?? json['calculated_cgst']),
      calculatedSgst: _num(calc?['sgst_amount'] ?? json['calculated_sgst']),
      calculatedIgst: _num(calc?['igst_amount'] ?? json['calculated_igst']),
      calculatedGstTotal: _num(calc?['gst_total'] ?? json['calculated_gst_total']),
      errors: (json['errors'] as List?)?.map((e) => e.toString()).toList() ?? [],
      warnings: (json['warnings'] as List?)?.map((w) => w.toString()).toList() ?? [],
      lineValidations: lv,
    );
  }
}

// ---------------------------------------------------------------------------
// Financial Validation & Mathematical Checks Models
// ---------------------------------------------------------------------------
class FinancialCheck {
  final String name;
  final String description;
  final String status; // PASSED, MISMATCH, REVIEW_REQUIRED, NOT_APPLICABLE
  final double? sourceValue;
  final double? calculatedValue;
  final double? difference;
  final String? note;

  FinancialCheck({
    required this.name,
    required this.description,
    required this.status,
    this.sourceValue,
    this.calculatedValue,
    this.difference,
    this.note,
  });

  factory FinancialCheck.fromJson(Map<String, dynamic> json) {
    double? _num(dynamic v) => v is num ? v.toDouble() : double.tryParse(v?.toString() ?? '');
    return FinancialCheck(
      name: json['name']?.toString() ?? 'Check',
      description: json['description']?.toString() ?? '',
      status: json['status']?.toString() ?? 'PASSED',
      sourceValue: _num(json['source_value']),
      calculatedValue: _num(json['calculated_value']),
      difference: _num(json['difference']),
      note: json['note']?.toString(),
    );
  }
}

class FinancialValidationResult {
  final String overallStatus; // PASSED, MISMATCH, REVIEW_REQUIRED
  final double tolerance;
  final Map<String, double?> source;
  final Map<String, double?> calculated;
  final Map<String, double?> differences;
  final List<FinancialCheck> checks;
  final List<String> errors;
  final List<String> warnings;

  FinancialValidationResult({
    required this.overallStatus,
    this.tolerance = 1.0,
    this.source = const {},
    this.calculated = const {},
    this.differences = const {},
    this.checks = const [],
    this.errors = const [],
    this.warnings = const [],
  });

  factory FinancialValidationResult.fromJson(Map<String, dynamic> json) {
    double? _num(dynamic v) => v is num ? v.toDouble() : double.tryParse(v?.toString() ?? '');

    final chkList = (json['checks'] as List?)
            ?.whereType<Map<String, dynamic>>()
            .map((c) => FinancialCheck.fromJson(c))
            .toList() ??
        [];

    final src = (json['source'] is Map<String, dynamic>)
        ? (json['source'] as Map<String, dynamic>).map((k, v) => MapEntry(k, _num(v)))
        : <String, double?>{};

    final calc = (json['calculated'] is Map<String, dynamic>)
        ? (json['calculated'] as Map<String, dynamic>).map((k, v) => MapEntry(k, _num(v)))
        : <String, double?>{};

    final diff = (json['differences'] is Map<String, dynamic>)
        ? (json['differences'] as Map<String, dynamic>).map((k, v) => MapEntry(k, _num(v)))
        : <String, double?>{};

    return FinancialValidationResult(
      overallStatus: json['overall_status']?.toString() ?? 'PASSED',
      tolerance: (json['tolerance'] is num) ? (json['tolerance'] as num).toDouble() : 1.0,
      source: src,
      calculated: calc,
      differences: diff,
      checks: chkList,
      errors: (json['errors'] as List?)?.map((e) => e.toString()).toList() ?? [],
      warnings: (json['warnings'] as List?)?.map((w) => w.toString()).toList() ?? [],
    );
  }
}

// ---------------------------------------------------------------------------
// Double-Entry Balanced Journal Models
// ---------------------------------------------------------------------------
class JournalLine {
  String accountCode;
  String accountName;
  String lineType; // EXPENSE, ASSET, INPUT_TAX, TDS_PAYABLE, ACCOUNTS_PAYABLE, ROUND_OFF
  double debit;
  double credit;
  int? sourceLineIndex;
  String provenance; // AI_PREDICTED, HITL_OVERRIDE, DETERMINISTIC
  String? description;

  JournalLine({
    required this.accountCode,
    required this.accountName,
    this.lineType = 'EXPENSE',
    this.debit = 0.0,
    this.credit = 0.0,
    this.sourceLineIndex,
    this.provenance = 'DETERMINISTIC',
    this.description,
  });

  static double _toDouble(dynamic val) {
    if (val == null) return 0.0;
    if (val is num) return val.toDouble();
    if (val is String) {
      final cleaned = val.replaceAll(',', '').replaceAll('₹', '').replaceAll('\$', '').trim();
      return double.tryParse(cleaned) ?? 0.0;
    }
    return 0.0;
  }

  factory JournalLine.fromJson(Map<String, dynamic> json) {
    final code = json['account_id']?.toString() ??
        json['account_code']?.toString() ??
        json['code']?.toString() ??
        json['accountId']?.toString() ??
        json['gl_code']?.toString() ??
        '';
    return JournalLine(
      accountCode: code,
      accountName: json['account_name']?.toString() ??
          json['account']?.toString() ??
          json['name']?.toString() ??
          json['gl_account']?.toString() ??
          'General Ledger Account',
      lineType: json['line_type']?.toString() ?? 'EXPENSE',
      debit: _toDouble(json['debit'] ?? json['debit_amount'] ?? json['dr'] ?? json['taxable_amount']),
      credit: _toDouble(json['credit'] ?? json['credit_amount'] ?? json['cr']),
      sourceLineIndex: json['source_line_index'] is int ? json['source_line_index'] : int.tryParse(json['source_line_index']?.toString() ?? ''),
      provenance: json['provenance']?.toString() ?? 'AI_PREDICTED',
      description: json['description']?.toString() ?? json['narration']?.toString() ?? json['notes']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'account_id': accountCode,
      'account_code': accountCode,
      'account_name': accountName,
      'line_type': lineType,
      'debit': debit,
      'credit': credit,
      'source_line_index': sourceLineIndex,
      'provenance': provenance,
      'description': description,
    };
  }
}

class JournalEntry {
  String? journalNumber;
  String? date;
  String? referenceNumber;
  String status; // BALANCED, APPROVED, REVIEW_REQUIRED, UNBALANCED
  String? approvalStatus;
  String? approvedBy;
  DateTime? approvedAt;
  List<JournalLine> lines;
  double totalDebit;
  double totalCredit;
  double difference;
  String currency;
  bool isBalanced;

  JournalEntry({
    this.journalNumber,
    this.date,
    this.referenceNumber,
    this.status = 'BALANCED',
    this.approvalStatus = 'PENDING',
    this.approvedBy,
    this.approvedAt,
    this.lines = const [],
    this.totalDebit = 0.0,
    this.totalCredit = 0.0,
    this.difference = 0.0,
    this.currency = 'INR',
    this.isBalanced = true,
  });

  factory JournalEntry.fromJson(Map<String, dynamic> json) {
    List<JournalLine> lines = [];
    final rawLines = json['lines'] ??
        json['journal_lines'] ??
        json['entries'] ??
        json['line_items'] ??
        json['accounting'] ??
        json['journal_entries'];

    if (rawLines is List) {
      lines = rawLines
          .whereType<Map<String, dynamic>>()
          .map((l) => JournalLine.fromJson(l))
          .toList();
    }

    double dr = 0.0;
    double cr = 0.0;
    for (final l in lines) {
      dr += l.debit;
      cr += l.credit;
    }

    if (json['total_debit'] != null) {
      dr = JournalLine._toDouble(json['total_debit']);
    }
    if (json['total_credit'] != null) {
      cr = JournalLine._toDouble(json['total_credit']);
    }

    final diff = (dr - cr).abs();
    final balanced = diff < 0.05;

    return JournalEntry(
      journalNumber: json['journal_number']?.toString() ??
          json['voucher_no']?.toString() ??
          json['number']?.toString() ??
          json['journal_id']?.toString() ??
          'JV-AUTO',
      date: json['date']?.toString() ?? json['journal_date']?.toString(),
      referenceNumber: json['reference_number']?.toString() ?? json['ref_no']?.toString(),
      status: json['status']?.toString() ?? (balanced ? 'BALANCED' : 'UNBALANCED'),
      approvalStatus: json['approval_status']?.toString() ?? 'PENDING',
      approvedBy: json['approved_by']?.toString(),
      approvedAt: json['approved_at'] != null ? DateTime.tryParse(json['approved_at'].toString()) : null,
      lines: lines,
      totalDebit: dr,
      totalCredit: cr,
      difference: diff,
      currency: json['currency']?.toString() ?? 'INR',
      isBalanced: json['is_balanced'] is bool ? json['is_balanced'] : balanced,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'journal_number': journalNumber,
      'date': date,
      'reference_number': referenceNumber,
      'status': status,
      'approval_status': approvalStatus,
      'approved_by': approvedBy,
      'approved_at': approvedAt?.toIso8601String(),
      'lines': lines.map((l) => l.toJson()).toList(),
      'total_debit': totalDebit,
      'total_credit': totalCredit,
      'difference': difference,
      'currency': currency,
      'is_balanced': isBalanced,
    };
  }
}

// ---------------------------------------------------------------------------
// Zoho Vendor Status Response
// ---------------------------------------------------------------------------
class MatchedVendor {
  final String? contactId;
  final String? contactName;
  final String? gstNo;
  final String? panNo;
  final String? email;
  final String? phone;

  MatchedVendor({
    this.contactId,
    this.contactName,
    this.gstNo,
    this.panNo,
    this.email,
    this.phone,
  });

  factory MatchedVendor.fromJson(Map<String, dynamic> json) {
    return MatchedVendor(
      contactId: json['contact_id']?.toString() ?? json['id']?.toString(),
      contactName: json['contact_name']?.toString() ?? json['name']?.toString(),
      gstNo: json['gst_no']?.toString() ?? json['gstin']?.toString(),
      panNo: json['pan_no']?.toString() ?? json['pan']?.toString(),
      email: json['email']?.toString(),
      phone: json['phone']?.toString() ?? json['mobile']?.toString(),
    );
  }
}

class InvoiceVendorStatusResponse {
  final String invoiceId;
  final bool isZohoConnected;
  final String matchStatus; // MATCHED, NOT_FOUND, MISMATCH, NOT_CONNECTED
  final Map<String, dynamic> invoiceVendor;
  final MatchedVendor? matchedVendor;
  final bool requiresAction;

  InvoiceVendorStatusResponse({
    required this.invoiceId,
    this.isZohoConnected = false,
    required this.matchStatus,
    this.invoiceVendor = const {},
    this.matchedVendor,
    this.requiresAction = false,
  });

  factory InvoiceVendorStatusResponse.fromJson(Map<String, dynamic> json) {
    return InvoiceVendorStatusResponse(
      invoiceId: json['invoice_id']?.toString() ?? '',
      isZohoConnected: json['is_zoho_connected'] == true,
      matchStatus: json['match_status']?.toString() ?? 'NOT_CONNECTED',
      invoiceVendor: (json['invoice_vendor'] as Map<String, dynamic>?) ?? {},
      matchedVendor: (json['matched_vendor'] is Map<String, dynamic>)
          ? MatchedVendor.fromJson(json['matched_vendor'])
          : null,
      requiresAction: json['requires_action'] == true,
    );
  }
}

// ---------------------------------------------------------------------------
// Master Invoice Entity
// ---------------------------------------------------------------------------
class Invoice {
  final dynamic id;
  final String? filename;
  final String? originalFilename;
  final String status;
  final String? approvalStatus;
  final String? accountingStatus;
  final String? exportStatus;
  final double? confidenceScore;
  final DateTime? createdAt;
  final DateTime? updatedAt;
  final ExtractedInvoiceData? extractedData;
  final TdsResult? tdsResult;
  final JournalEntry? journalEntry;
  final GstResult? gstResult;
  final ItcResult? itcResult;
  final FinancialValidationResult? financialValidationResult;
  final String? zohoBillId;
  final String? zohoBillNumber;
  final String? zohoStatus;
  final String? reviewReason;
  final bool needsReview;
  final String? periodCategory;
  final String? periodDecision;
  final String? invoiceOrigin;
  final String? currency;

  // Classification & Audit Fields
  final double? classificationConfidence;
  final String? classificationReason;
  final String? classificationSource;
  final String? classificationOverride;
  final String? classificationOverrideReason;
  final String? classifiedBy;
  final DateTime? classifiedAt;

  // Foreign Currency & FX Fields (Step 1 Foundation)
  final String? originalCurrency;
  final double? originalTotalAmount;
  final double? originalTaxableAmount;
  final double? exchangeRate;
  final String? exchangeRateDate;
  final String? exchangeRateSource;
  final double? convertedTotalInr;
  final double? convertedTaxableInr;
  final bool fxRateOverridden;
  final String? fxOverrideReason;
  final double? fxOriginalRate;
  final String? vendorCountry;
  final String? vendorTaxId;
  final String? servicePeriod;
  final String? serviceDescription;

  Invoice({
    required this.id,
    this.filename,
    this.originalFilename,
    required this.status,
    this.approvalStatus,
    this.accountingStatus,
    this.exportStatus,
    this.confidenceScore,
    this.createdAt,
    this.updatedAt,
    this.extractedData,
    this.tdsResult,
    this.journalEntry,
    this.gstResult,
    this.itcResult,
    this.financialValidationResult,
    this.zohoBillId,
    this.zohoBillNumber,
    this.zohoStatus,
    this.reviewReason,
    this.needsReview = false,
    this.periodCategory,
    this.periodDecision,
    this.invoiceOrigin = 'INDIAN',
    this.currency = 'INR',
    this.classificationConfidence,
    this.classificationReason,
    this.classificationSource = 'SYSTEM',
    this.classificationOverride,
    this.classificationOverrideReason,
    this.classifiedBy,
    this.classifiedAt,
    this.originalCurrency = 'INR',
    this.originalTotalAmount,
    this.originalTaxableAmount,
    this.exchangeRate = 1.0,
    this.exchangeRateDate,
    this.exchangeRateSource,
    this.convertedTotalInr,
    this.convertedTaxableInr,
    this.fxRateOverridden = false,
    this.fxOverrideReason,
    this.fxOriginalRate,
    this.vendorCountry,
    this.vendorTaxId,
    this.servicePeriod,
    this.serviceDescription,
  });

  bool get isIndian => (invoiceOrigin?.toUpperCase() ?? 'INDIAN') == 'INDIAN';
  bool get isForeignService => (invoiceOrigin?.toUpperCase() ?? '') == 'FOREIGN_SERVICE' || (invoiceOrigin?.toUpperCase() ?? '') == 'FOREIGN';
  bool get isUnsupportedGoods => (invoiceOrigin?.toUpperCase() ?? '') == 'UNSUPPORTED_FOREIGN_GOODS';
  bool get isReviewRequired => (invoiceOrigin?.toUpperCase() ?? '') == 'REVIEW_REQUIRED';
  bool get isForeign => isForeignService || isUnsupportedGoods;

  String get displayStatus {
    final exp = (exportStatus ?? zohoStatus ?? '').toUpperCase();
    if (exp == 'EXPORTED' || (zohoBillId != null && zohoBillId!.isNotEmpty)) {
      return 'exported';
    }
    final appr = (approvalStatus ?? '').toUpperCase();
    if (appr == 'APPROVED') {
      return 'approved';
    }
    if (appr == 'REJECTED' || status.toUpperCase() == 'FAILED' || exp == 'FAILED') {
      return 'failed';
    }
    if (status.toUpperCase().startsWith('PROCESSING')) {
      return 'processing';
    }
    return 'pending';
  }

  static double? _toDouble(dynamic val) {
    if (val == null) return null;
    if (val is num) return val.toDouble();
    if (val is String) {
      final cleaned = val.replaceAll(',', '').replaceAll('₹', '').replaceAll('\$', '').trim();
      return double.tryParse(cleaned);
    }
    return null;
  }

  factory Invoice.fromJson(Map<String, dynamic> json) {
    ExtractedInvoiceData? extData;

    if (json['current_vlm_output'] is Map<String, dynamic>) {
      final vlm = json['current_vlm_output'] as Map<String, dynamic>;
      final inner = (vlm['data'] is Map<String, dynamic>) ? vlm['data'] as Map<String, dynamic> : vlm;
      extData = ExtractedInvoiceData.fromJson(inner);
    } else if (json['raw_vlm_output'] is Map<String, dynamic>) {
      final vlm = json['raw_vlm_output'] as Map<String, dynamic>;
      final inner = (vlm['data'] is Map<String, dynamic>) ? vlm['data'] as Map<String, dynamic> : vlm;
      extData = ExtractedInvoiceData.fromJson(inner);
    } else if (json['extracted_data'] is Map<String, dynamic>) {
      extData = ExtractedInvoiceData.fromJson(json['extracted_data']);
    } else if (json['data'] is Map<String, dynamic>) {
      extData = ExtractedInvoiceData.fromJson(json['data']);
    } else {
      extData = ExtractedInvoiceData.fromJson(json);
    }

    // Populate missing extracted values from top-level response fields
    if (extData.vendorName == null || extData.vendorName!.trim().isEmpty) {
      extData.vendorName = json['vendor_name']?.toString() ?? json['supplier_name']?.toString();
    }
    if (extData.invoiceNumber == null || extData.invoiceNumber!.trim().isEmpty) {
      extData.invoiceNumber = json['invoice_number']?.toString() ?? json['invoice_no']?.toString();
    }
    if (extData.totalAmount == null || extData.totalAmount == 0.0) {
      extData.totalAmount = _toDouble(json['total_amount'] ?? json['grand_total'] ?? json['total']);
    }

    GstResult? gst;
    if (json['gst_result'] is Map<String, dynamic>) {
      gst = GstResult.fromJson(json['gst_result']);
    } else if (json['gst_rcm'] is Map<String, dynamic>) {
      gst = GstResult.fromJson(json['gst_rcm']);
    } else if (json['current_accounting_output'] is Map<String, dynamic>) {
      final acct = json['current_accounting_output'] as Map<String, dynamic>;
      if (acct['gst_result'] is Map<String, dynamic>) {
        gst = GstResult.fromJson(acct['gst_result']);
      } else if (acct['gst_rcm'] is Map<String, dynamic>) {
        gst = GstResult.fromJson(acct['gst_rcm']);
      } else if (acct['gst_engine'] is Map<String, dynamic>) {
        gst = GstResult.fromJson(acct['gst_engine']);
      }
    } else if (json['accounting_output'] is Map<String, dynamic>) {
      final acct = json['accounting_output'] as Map<String, dynamic>;
      if (acct['gst_result'] is Map<String, dynamic>) {
        gst = GstResult.fromJson(acct['gst_result']);
      } else if (acct['gst_rcm'] is Map<String, dynamic>) {
        gst = GstResult.fromJson(acct['gst_rcm']);
      } else if (acct['gst_engine'] is Map<String, dynamic>) {
        gst = GstResult.fromJson(acct['gst_engine']);
      }
    }

    ItcResult? itc;
    if (json['itc_result'] is Map<String, dynamic>) {
      itc = ItcResult.fromJson(json['itc_result']);
    } else if (json['itc_assessment'] is Map<String, dynamic>) {
      itc = ItcResult.fromJson(json['itc_assessment']);
    } else if (json['current_accounting_output'] is Map<String, dynamic>) {
      final acct = json['current_accounting_output'] as Map<String, dynamic>;
      if (acct['itc_assessment'] is Map<String, dynamic>) {
        itc = ItcResult.fromJson(acct['itc_assessment']);
      } else if (acct['itc_result'] is Map<String, dynamic>) {
        itc = ItcResult.fromJson(acct['itc_result']);
      }
    } else if (json['accounting_output'] is Map<String, dynamic>) {
      final acct = json['accounting_output'] as Map<String, dynamic>;
      if (acct['itc_assessment'] is Map<String, dynamic>) {
        itc = ItcResult.fromJson(acct['itc_assessment']);
      } else if (acct['itc_result'] is Map<String, dynamic>) {
        itc = ItcResult.fromJson(acct['itc_result']);
      }
    }

    FinancialValidationResult? fvr;
    if (json['financial_validation_result'] is Map<String, dynamic>) {
      fvr = FinancialValidationResult.fromJson(json['financial_validation_result']);
    } else if (json['financial_validation'] is Map<String, dynamic>) {
      fvr = FinancialValidationResult.fromJson(json['financial_validation']);
    } else if (json['current_accounting_output'] is Map<String, dynamic>) {
      final acct = json['current_accounting_output'] as Map<String, dynamic>;
      if (acct['financial_validation_result'] is Map<String, dynamic>) {
        fvr = FinancialValidationResult.fromJson(acct['financial_validation_result']);
      } else if (acct['financial_validation'] is Map<String, dynamic>) {
        fvr = FinancialValidationResult.fromJson(acct['financial_validation']);
      }
    } else if (json['accounting_output'] is Map<String, dynamic>) {
      final acct = json['accounting_output'] as Map<String, dynamic>;
      if (acct['financial_validation_result'] is Map<String, dynamic>) {
        fvr = FinancialValidationResult.fromJson(acct['financial_validation_result']);
      } else if (acct['financial_validation'] is Map<String, dynamic>) {
        fvr = FinancialValidationResult.fromJson(acct['financial_validation']);
      }
    }

    if (gst != null) {
      if ((extData.cgstAmount == null || extData.cgstAmount == 0.0) && (gst.extractedCgst ?? gst.calculatedCgst ?? 0.0) > 0) {
        extData.cgstAmount = gst.extractedCgst ?? gst.calculatedCgst;
      }
      if ((extData.sgstAmount == null || extData.sgstAmount == 0.0) && (gst.extractedSgst ?? gst.calculatedSgst ?? 0.0) > 0) {
        extData.sgstAmount = gst.extractedSgst ?? gst.calculatedSgst;
      }
      if ((extData.igstAmount == null || extData.igstAmount == 0.0) && (gst.extractedIgst ?? gst.calculatedIgst ?? 0.0) > 0) {
        extData.igstAmount = gst.extractedIgst ?? gst.calculatedIgst;
      }
      if ((extData.taxTotal == null || extData.taxTotal == 0.0) && (gst.extractedTaxTotal ?? gst.calculatedGstTotal ?? 0.0) > 0) {
        extData.taxTotal = gst.extractedTaxTotal ?? gst.calculatedGstTotal;
      }
    }
    if (fvr != null) {
      if (extData.totalAmount == null || extData.totalAmount == 0.0) {
        extData.totalAmount = _toDouble(fvr.calculated['grand_total'] ?? fvr.source['total_amount']);
      }
      if (extData.taxableAmount == null || extData.taxableAmount == 0.0) {
        extData.taxableAmount = _toDouble(fvr.calculated['subtotal'] ?? fvr.source['subtotal']);
      }
    }

    TdsResult? tds;
    if (json['tds_result'] is Map<String, dynamic>) {
      tds = TdsResult.fromJson(json['tds_result']);
    } else if (json['tds'] is Map<String, dynamic>) {
      tds = TdsResult.fromJson(json['tds']);
    } else if (json['current_accounting_output'] is Map<String, dynamic>) {
      final acct = json['current_accounting_output'] as Map<String, dynamic>;
      final tdsObj = acct['tds_final'] ?? acct['tds'] ?? acct['tds_assessment'];
      if (tdsObj is Map<String, dynamic>) {
        tds = TdsResult.fromJson(tdsObj);
      }
    } else if (json['accounting_output'] is Map<String, dynamic>) {
      final acct = json['accounting_output'] as Map<String, dynamic>;
      final tdsObj = acct['tds_final'] ?? acct['tds'] ?? acct['tds_assessment'];
      if (tdsObj is Map<String, dynamic>) {
        tds = TdsResult.fromJson(tdsObj);
      }
    }

    JournalEntry? journal;
    if (json['journal_entry'] is Map<String, dynamic>) {
      journal = JournalEntry.fromJson(json['journal_entry']);
    } else if (json['journal'] is Map<String, dynamic>) {
      journal = JournalEntry.fromJson(json['journal']);
    } else if (json['current_accounting_output'] is Map<String, dynamic>) {
      final acct = json['current_accounting_output'] as Map<String, dynamic>;
      if (acct['journal_entry'] is Map<String, dynamic>) {
        journal = JournalEntry.fromJson(acct['journal_entry']);
      }
    } else if (json['accounting_output'] is Map<String, dynamic>) {
      final acct = json['accounting_output'] as Map<String, dynamic>;
      if (acct['journal_entry'] is Map<String, dynamic>) {
        journal = JournalEntry.fromJson(acct['journal_entry']);
      }
    }

    final apprStatus = json['approval_status']?.toString();
    final rawStatus = json['status']?.toString() ?? 'pending';

    return Invoice(
      id: json['id']?.toString() ?? json['invoice_id']?.toString() ?? json['_id']?.toString() ?? '',
      filename: json['filename']?.toString() ?? json['file_name']?.toString() ?? json['original_filename']?.toString(),
      originalFilename: json['original_filename']?.toString() ?? json['file_name']?.toString(),
      status: rawStatus,
      approvalStatus: apprStatus,
      accountingStatus: json['accounting_status']?.toString(),
      exportStatus: json['export_status']?.toString(),
      confidenceScore: _toDouble(json['confidence_score'] ?? json['accounting_confidence'] ?? json['confidence']),
      createdAt: json['created_at'] != null ? DateTime.tryParse(json['created_at'].toString()) : null,
      updatedAt: json['updated_at'] != null ? DateTime.tryParse(json['updated_at'].toString()) : null,
      extractedData: extData,
      tdsResult: tds,
      journalEntry: journal,
      gstResult: gst,
      itcResult: itc,
      financialValidationResult: fvr,
      zohoBillId: json['zoho_bill_id']?.toString() ?? json['zoho_bill_number']?.toString(),
      zohoBillNumber: json['zoho_bill_number']?.toString() ?? json['zoho_bill_id']?.toString(),
      zohoStatus: json['zoho_status']?.toString() ?? json['export_status']?.toString(),
      reviewReason: json['review_reason']?.toString(),
      needsReview: json['needs_review'] ?? (apprStatus == 'PENDING_REVIEW' || rawStatus.toLowerCase().contains('pending')),
      periodCategory: json['period_category']?.toString(),
      periodDecision: json['period_decision']?.toString(),
      invoiceOrigin: json['invoice_origin']?.toString() ?? 'INDIAN',
      currency: json['currency']?.toString() ?? extData.currency ?? 'INR',
      classificationConfidence: _toDouble(json['classification_confidence']),
      classificationReason: json['classification_reason']?.toString(),
      classificationSource: json['classification_source']?.toString() ?? 'SYSTEM',
      classificationOverride: json['classification_override']?.toString(),
      classificationOverrideReason: json['classification_override_reason']?.toString(),
      classifiedBy: json['classified_by']?.toString(),
      classifiedAt: json['classified_at'] != null ? DateTime.tryParse(json['classified_at'].toString()) : null,
      originalCurrency: json['original_currency']?.toString() ??
          json['currency']?.toString() ??
          extData.originalCurrency ??
          'INR',
      originalTotalAmount: _toDouble(json['original_total_amount']) ?? extData.originalTotalAmount,
      originalTaxableAmount: _toDouble(json['original_taxable_amount']) ?? extData.originalTaxableAmount,
      exchangeRate: _toDouble(json['exchange_rate']) ?? extData.exchangeRate ?? 1.0,
      exchangeRateDate: json['exchange_rate_date']?.toString() ?? extData.exchangeRateDate,
      exchangeRateSource: json['exchange_rate_source']?.toString() ?? extData.exchangeRateSource,
      convertedTotalInr: _toDouble(json['converted_total_inr']) ?? extData.convertedTotalInr,
      convertedTaxableInr: _toDouble(json['converted_taxable_inr']) ?? extData.convertedTaxableInr,
      fxRateOverridden: json['fx_rate_overridden'] == true || extData.fxRateOverridden == true,
      fxOverrideReason: json['fx_override_reason']?.toString() ?? extData.fxOverrideReason,
      fxOriginalRate: _toDouble(json['fx_original_rate']) ?? extData.fxOriginalRate,
      vendorCountry: json['vendor_country']?.toString() ?? extData.vendorCountry,
      vendorTaxId: json['vendor_tax_id']?.toString() ?? extData.vendorTaxId,
      servicePeriod: json['service_period']?.toString() ?? extData.servicePeriod,
      serviceDescription: json['service_description']?.toString() ?? extData.serviceDescription,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'filename': filename,
      'original_filename': originalFilename,
      'status': status,
      'approval_status': approvalStatus,
      'accounting_status': accountingStatus,
      'export_status': exportStatus,
      'confidence_score': confidenceScore,
      'created_at': createdAt?.toIso8601String(),
      'updated_at': updatedAt?.toIso8601String(),
      'extracted_data': extractedData?.toJson(),
      'tds_result': tdsResult?.toJson(),
      'journal_entry': journalEntry?.toJson(),
      'itc_result': itcResult?.toJson(),
      'zoho_bill_id': zohoBillId,
      'zoho_bill_number': zohoBillNumber,
      'zoho_status': zohoStatus,
      'review_reason': reviewReason,
      'needs_review': needsReview,
      'period_category': periodCategory,
      'period_decision': periodDecision,
      'invoice_origin': invoiceOrigin,
      'currency': currency,
      'original_currency': originalCurrency,
      'original_total_amount': originalTotalAmount,
      'original_taxable_amount': originalTaxableAmount,
      'exchange_rate': exchangeRate,
      'exchange_rate_date': exchangeRateDate,
      'exchange_rate_source': exchangeRateSource,
      'converted_total_inr': convertedTotalInr,
      'converted_taxable_inr': convertedTaxableInr,
      'fx_rate_overridden': fxRateOverridden,
      'fx_override_reason': fxOverrideReason,
      'fx_original_rate': fxOriginalRate,
      'vendor_country': vendorCountry,
      'vendor_tax_id': vendorTaxId,
      'service_period': servicePeriod,
      'service_description': serviceDescription,
    };
  }
}
