import 'dart:js_interop';
import 'dart:typed_data';
import 'dart:ui_web' as ui_web;
import 'package:flutter/material.dart';
import 'package:web/web.dart' as web;

final Set<String> _registeredViews = {};

Widget buildPdfFrame({
  required String url,
  required String viewId,
  required Uint8List? bytes,
}) {
  final uniqueId = 'pdf-frame-$viewId';
  if (!_registeredViews.contains(uniqueId)) {
    ui_web.platformViewRegistry.registerViewFactory(uniqueId, (int id) {
      final iframe = web.HTMLIFrameElement();
      if (bytes != null && bytes.isNotEmpty) {
        final jsArray = bytes.toJS;
        final parts = [jsArray].toJS;
        final blob = web.Blob(parts, web.BlobPropertyBag(type: 'application/pdf'));
        final blobUrl = web.URL.createObjectURL(blob);
        iframe.src = blobUrl;
      } else {
        iframe.src = url;
      }
      iframe.style.border = 'none';
      iframe.style.width = '100%';
      iframe.style.height = '100%';
      return iframe;
    });
    _registeredViews.add(uniqueId);
  }

  return HtmlElementView(viewType: uniqueId);
}

void openBlobInNewTab(Uint8List bytes, String mimeType) {
  final jsArray = bytes.toJS;
  final parts = [jsArray].toJS;
  final blob = web.Blob(parts, web.BlobPropertyBag(type: mimeType.isNotEmpty ? mimeType : 'application/pdf'));
  final blobUrl = web.URL.createObjectURL(blob);
  web.window.open(blobUrl, '_blank');
}
