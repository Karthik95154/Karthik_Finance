import 'package:web/web.dart' as web;

void openWebPopupWindow(String url) {
  try {
    web.window.open(
      url,
      'zoho_oauth_popup',
      'width=640,height=800,top=100,left=300,menubar=no,toolbar=no,location=no,status=no,resizable=yes,scrollbars=yes',
    );
  } catch (_) {}
}
