class ForexRate {
  final String currency;
  final String targetCurrency;
  final double rate;
  final String rateFormatted;
  final String rateDate;
  final String source;
  final bool isFallback;
  final String status;

  ForexRate({
    required this.currency,
    this.targetCurrency = 'INR',
    required this.rate,
    required this.rateFormatted,
    required this.rateDate,
    required this.source,
    this.isFallback = false,
    this.status = 'LIVE',
  });

  factory ForexRate.fromJson(Map<String, dynamic> json) {
    return ForexRate(
      currency: json['currency']?.toString() ?? '',
      targetCurrency: json['target_currency']?.toString() ?? 'INR',
      rate: (json['rate'] as num?)?.toDouble() ?? 1.0,
      rateFormatted: json['rate_formatted']?.toString() ?? '',
      rateDate: json['rate_date']?.toString() ?? '',
      source: json['source']?.toString() ?? '',
      isFallback: json['is_fallback'] == true,
      status: json['status']?.toString() ?? 'LIVE',
    );
  }
}

class ForexRatesResponse {
  final String base;
  final String date;
  final String lastUpdated;
  final List<ForexRate> rates;
  final List<String> rbiReferenceCurrencies;

  ForexRatesResponse({
    this.base = 'INR',
    required this.date,
    required this.lastUpdated,
    required this.rates,
    required this.rbiReferenceCurrencies,
  });

  factory ForexRatesResponse.fromJson(Map<String, dynamic> json) {
    final list = json['rates'] as List<dynamic>? ?? [];
    final rates = list.map((e) => ForexRate.fromJson(e as Map<String, dynamic>)).toList();
    final rbiList = (json['rbi_reference_currencies'] as List<dynamic>? ?? [])
        .map((e) => e.toString())
        .toList();

    return ForexRatesResponse(
      base: json['base']?.toString() ?? 'INR',
      date: json['date']?.toString() ?? '',
      lastUpdated: json['last_updated']?.toString() ?? '',
      rates: rates,
      rbiReferenceCurrencies: rbiList,
    );
  }
}
