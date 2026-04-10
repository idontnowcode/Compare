"""FTP/SFTP 원격 파일 비교 다이얼로그."""
import os
import tempfile
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QTreeWidget, QTreeWidgetItem,
    QMessageBox, QProgressBar, QComboBox, QCheckBox,
    QDialogButtonBox, QGroupBox, QFormLayout, QSplitter,
    QAbstractItemView, QHeaderView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False


class SFTPWorker(QThread):
    """백그라운드 SFTP 연결 및 파일 목록 조회."""
    connected    = pyqtSignal()
    file_listed  = pyqtSignal(list)   # list of (name, size, is_dir)
    file_fetched = pyqtSignal(str)    # local temp path
    error        = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._host = ""
        self._port = 22
        self._user = ""
        self._password = ""
        self._key_path = ""
        self._remote_path = "/"
        self._mode = "connect"
        self._ssh: "paramiko.SSHClient | None" = None
        self._sftp: "paramiko.SFTPClient | None" = None
        self._fetch_remote = ""

    def setup_connect(self, host, port, user, password, key_path):
        self._host = host; self._port = port
        self._user = user; self._password = password
        self._key_path = key_path
        self._mode = "connect"

    def setup_list(self, remote_path: str):
        self._remote_path = remote_path
        self._mode = "list"

    def setup_fetch(self, remote_path: str):
        self._fetch_remote = remote_path
        self._mode = "fetch"

    def run(self):
        if not PARAMIKO_AVAILABLE:
            self.error.emit("paramiko 라이브러리가 없습니다: pip install paramiko")
            return
        try:
            if self._mode == "connect":
                self._do_connect()
            elif self._mode == "list":
                self._do_list()
            elif self._mode == "fetch":
                self._do_fetch()
        except Exception as e:
            self.error.emit(str(e))

    def _do_connect(self):
        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kwargs = dict(hostname=self._host, port=self._port, username=self._user)
        if self._key_path:
            kwargs["key_filename"] = self._key_path
        else:
            kwargs["password"] = self._password
        self._ssh.connect(**kwargs, timeout=10)
        self._sftp = self._ssh.open_sftp()
        self.connected.emit()

    def _do_list(self):
        if self._sftp is None:
            raise RuntimeError("연결되지 않음")
        items = []
        for attr in self._sftp.listdir_attr(self._remote_path):
            import stat
            is_dir = stat.S_ISDIR(attr.st_mode) if attr.st_mode else False
            items.append((attr.filename, attr.st_size or 0, is_dir))
        items.sort(key=lambda x: (not x[2], x[0].lower()))
        self.file_listed.emit(items)

    def _do_fetch(self):
        if self._sftp is None:
            raise RuntimeError("연결되지 않음")
        suffix = os.path.splitext(self._fetch_remote)[1]
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.close()
        self._sftp.get(self._fetch_remote, tmp.name)
        self.file_fetched.emit(tmp.name)

    def disconnect(self):
        if self._sftp:
            self._sftp.close()
        if self._ssh:
            self._ssh.close()


class FTPDialog(QDialog):
    """SFTP 연결 및 파일 선택 다이얼로그. 선택한 파일의 로컬 임시 경로를 반환."""

    files_selected = pyqtSignal(str, str)   # (local_left_tmp, local_right_tmp)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SFTP 원격 파일 비교")
        self.resize(700, 500)
        self._worker = SFTPWorker()
        self._worker.connected.connect(self._on_connected)
        self._worker.file_listed.connect(self._on_listed)
        self._worker.file_fetched.connect(self._on_fetched)
        self._worker.error.connect(self._on_error)
        self._tmp_left  = ""
        self._tmp_right = ""
        self._fetching  = ""   # "left" | "right"
        self._cur_path  = "/"
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)

        # 연결 정보
        grp = QGroupBox("SFTP 연결")
        form = QFormLayout(grp)

        self._inp_host = QLineEdit(); self._inp_host.setPlaceholderText("hostname or IP")
        self._inp_port = QSpinBox(); self._inp_port.setRange(1, 65535); self._inp_port.setValue(22)
        self._inp_user = QLineEdit()
        self._inp_pass = QLineEdit(); self._inp_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._inp_key  = QLineEdit(); self._inp_key.setPlaceholderText("(선택) 개인키 경로")

        form.addRow("호스트:", self._inp_host)
        form.addRow("포트:",   self._inp_port)
        form.addRow("사용자:", self._inp_user)
        form.addRow("비밀번호:", self._inp_pass)
        form.addRow("키 파일:", self._inp_key)
        root.addWidget(grp)

        # 연결 버튼
        self._btn_connect = QPushButton("연결"); self._btn_connect.clicked.connect(self._connect)
        self._prog = QProgressBar(); self._prog.setRange(0, 0); self._prog.hide()
        row = QHBoxLayout()
        row.addWidget(self._btn_connect); row.addWidget(self._prog); row.addStretch()
        root.addLayout(row)

        # 파일 브라우저
        self._lbl_path = QLabel("/")
        root.addWidget(self._lbl_path)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(3)
        self._tree.setHeaderLabels(["이름", "크기", "종류"])
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tree.itemDoubleClicked.connect(self._on_item_dbl)
        root.addWidget(self._tree)

        # 파일 선택 버튼
        row2 = QHBoxLayout()
        self._btn_pick_left  = QPushButton("← 왼쪽으로 선택"); self._btn_pick_left.clicked.connect(self._pick_left)
        self._btn_pick_right = QPushButton("오른쪽으로 선택 →"); self._btn_pick_right.clicked.connect(self._pick_right)
        self._lbl_sel = QLabel("")
        for w in [self._btn_pick_left, self._btn_pick_right, self._lbl_sel]:
            row2.addWidget(w)
        row2.addStretch()
        root.addLayout(row2)

        # 확인/취소
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        if not PARAMIKO_AVAILABLE:
            self._btn_connect.setEnabled(False)
            self._btn_connect.setText("paramiko 없음 (pip install paramiko)")

    def _connect(self):
        self._prog.show()
        self._btn_connect.setEnabled(False)
        self._worker.setup_connect(
            self._inp_host.text(), self._inp_port.value(),
            self._inp_user.text(), self._inp_pass.text(),
            self._inp_key.text()
        )
        self._worker.start()

    def _on_connected(self):
        self._prog.hide()
        self._btn_connect.setEnabled(True)
        self._list_dir("/")

    def _list_dir(self, path: str):
        self._cur_path = path
        self._lbl_path.setText(path)
        self._worker.setup_list(path)
        self._worker.start()

    def _on_listed(self, items: list):
        self._tree.clear()
        if self._cur_path != "/":
            up = QTreeWidgetItem(self._tree)
            up.setText(0, ".. (위로)")
            up.setData(0, Qt.ItemDataRole.UserRole, ("dir", os.path.dirname(self._cur_path)))
        for name, size, is_dir in items:
            item = QTreeWidgetItem(self._tree)
            icon = "📁 " if is_dir else "📄 "
            item.setText(0, icon + name)
            item.setText(1, "" if is_dir else f"{size:,}")
            item.setText(2, "폴더" if is_dir else "파일")
            full = self._cur_path.rstrip("/") + "/" + name
            item.setData(0, Qt.ItemDataRole.UserRole, ("dir" if is_dir else "file", full))

    def _on_item_dbl(self, item: QTreeWidgetItem, _col: int):
        kind, path = item.data(0, Qt.ItemDataRole.UserRole)
        if kind == "dir":
            self._list_dir(path)

    def _pick_left(self):
        item = self._tree.currentItem()
        if item is None: return
        kind, path = item.data(0, Qt.ItemDataRole.UserRole)
        if kind != "file": return
        self._fetching = "left"
        self._worker.setup_fetch(path)
        self._worker.start()

    def _pick_right(self):
        item = self._tree.currentItem()
        if item is None: return
        kind, path = item.data(0, Qt.ItemDataRole.UserRole)
        if kind != "file": return
        self._fetching = "right"
        self._worker.setup_fetch(path)
        self._worker.start()

    def _on_fetched(self, tmp_path: str):
        if self._fetching == "left":
            self._tmp_left = tmp_path
        else:
            self._tmp_right = tmp_path
        self._lbl_sel.setText(f"좌: {bool(self._tmp_left)} / 우: {bool(self._tmp_right)}")

    def _on_error(self, msg: str):
        self._prog.hide()
        self._btn_connect.setEnabled(True)
        QMessageBox.critical(self, "오류", msg)

    def _on_ok(self):
        if self._tmp_left and self._tmp_right:
            self._worker.disconnect()
            self.files_selected.emit(self._tmp_left, self._tmp_right)
            self.accept()
        else:
            QMessageBox.warning(self, "선택 필요", "왼쪽과 오른쪽 파일을 모두 선택해주세요.")
