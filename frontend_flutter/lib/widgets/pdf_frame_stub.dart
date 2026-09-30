import 'dart:typed_data';
import 'package:flutter/material.dart';

Widget buildPdfFrame({
  required String url,
  required String viewId,
  required Uint8List? bytes,
}) {
  return const Center(
    child: Text('PDF preview is only supported in browser mode.'),
  );
}

void openBlobInNewTab(Uint8List bytes, String mimeType) {
  // Stub for non-web environments
}
