import 'dart:convert';

import 'package:http/http.dart' as http;

// Backend base URL.
//   - Web / Windows desktop / iOS simulator: the FastAPI server's own host.
//   - Android emulator: 10.0.2.2 is the special alias for the host machine's
//     localhost, so http://127.0.0.1:8000 from the emulator would NOT reach
//     the server running on your PC.
const String apiBaseUrl = 'http://127.0.0.1:8000';

/// FastAPI's own errors come back as JSON (`{"detail": "..."}`), but an
/// unhandled server crash or a proxy in between can return a plain-text
/// body instead - decoding that as JSON would throw a second, more
/// confusing error on top of the original one. Fall back to the raw text.
String extractErrorDetail(http.Response response) {
  try {
    final body = jsonDecode(response.body);
    if (body is Map && body['detail'] != null) return body['detail'].toString();
  } catch (_) {
    // Not JSON - fall through to the raw body below.
  }
  final text = response.body.trim();
  return text.isNotEmpty ? text : 'Request failed (${response.statusCode})';
}
