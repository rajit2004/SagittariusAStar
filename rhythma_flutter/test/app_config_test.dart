import 'package:flutter_test/flutter_test.dart';
import 'package:rhythma/config/app_config.dart';

void main() {
  test('default API base URL must use HTTPS for release builds', () {
    
    expect(
      AppConfig.apiBaseUrl.startsWith('https://'),
      isTrue,
      reason: 'The default API_BASE_URL must be HTTPS. '
          'Pass --dart-define=API_BASE_URL=http://... for local development.',
    );
  });
}
