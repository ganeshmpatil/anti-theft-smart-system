import 'package:flutter_test/flutter_test.dart';
import 'package:farm_guard/main.dart';

void main() {
  testWidgets('App starts without crashing', (WidgetTester tester) async {
    await tester.pumpWidget(const FarmGuardApp());
    expect(find.byType(FarmGuardApp), findsOneWidget);
  });
}
