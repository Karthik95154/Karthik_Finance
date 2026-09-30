import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/main.dart';

void main() {
  testWidgets('App smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const SakshiFinanceApp());
    expect(find.byType(SakshiFinanceApp), findsOneWidget);
  });
}
