from krita import Krita, Extension

from .dialog import SpineExportDialog


class KritaSpineExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)

    def setup(self):
        pass

    def createActions(self, window):
        action = window.createAction(
            "spine_export",
            "Export to Spine...",
            "tools/scripts",
        )
        action.triggered.connect(self._show_export_dialog)

    def _show_export_dialog(self):
        app = Krita.instance()
        document = app.activeDocument()
        if document is None:
            app.activeWindow().qwindow().showMessage(
                "Open a document before exporting to Spine."
            )
            return
        dialog = SpineExportDialog(document, app.activeWindow().qwindow())
        dialog.exec_()


app = Krita.instance()
app.addExtension(KritaSpineExtension(app))
