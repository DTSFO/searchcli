import os
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

class Config:
    _instance = None
    _SETUP_HINT = "Run 'grok-search config import-env FILE' or export GROK_API_URL and GROK_API_KEY."
    _DEFAULT_MODEL = "grok-4.20-beta"
    _DEFAULT_GUDA_BASE_URL = "https://code.guda.studio"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config_file = None
            cls._instance._cached_model = None
            cls._instance._env_loaded = False
        return cls._instance

    @property
    def env_file(self) -> Path:
        return self.config_file.parent / "env"

    def _load_env_file(self) -> None:
        if self._env_loaded:
            return
        self._env_loaded = True
        if not self.env_file.exists():
            return
        try:
            for raw_line in self.env_file.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, value = line.split("=", 1)
                name = name.strip()
                value = value.strip().strip('"').strip("'")
                if name == "TAVILY_URL":
                    name = "TAVILY_API_URL"
                if name and value:
                    os.environ.setdefault(name, value)
        except OSError:
            return

    def import_env_file(self, source: Path) -> dict:
        allowed = {
            "GUDA_API_KEY", "GUDA_BASE_URL", "GROK_API_URL", "GROK_API_KEY", "GROK_MODEL",
            "TAVILY_API_URL", "TAVILY_URL", "TAVILY_API_KEY", "TAVILY_ENABLED",
            "FIRECRAWL_API_URL", "FIRECRAWL_API_KEY", "GROK_DEBUG", "GROK_LOG_LEVEL",
            "GROK_LOG_DIR", "GROK_RETRY_MAX_ATTEMPTS", "GROK_RETRY_MULTIPLIER", "GROK_RETRY_MAX_WAIT",
        }
        values: dict[str, str] = {}
        for raw_line in source.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            name = name.strip()
            if name not in allowed:
                continue
            normalized = "TAVILY_API_URL" if name == "TAVILY_URL" else name
            values[normalized] = value.strip().strip('"').strip("'")
        self.env_file.parent.mkdir(parents=True, exist_ok=True)
        temp = self.env_file.with_suffix(".tmp")
        temp.write_text("".join(f"{name}={value}\n" for name, value in values.items()), encoding="utf-8")
        os.chmod(temp, 0o600)
        os.replace(temp, self.env_file)
        self._env_loaded = False
        self._cached_model = None
        self._load_env_file()
        return {"file": str(self.env_file), "variables": sorted(values), "count": len(values)}

    @property
    def config_file(self) -> Path:
        if self._config_file is None:
            config_dir = Path.home() / ".config" / "grok-search"
            try:
                config_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                config_dir = Path.cwd() / ".grok-search"
                config_dir.mkdir(parents=True, exist_ok=True)
            self._config_file = config_dir / "config.json"
        return self._config_file

    def _load_config_file(self) -> dict:
        if not self.config_file.exists():
            return {}
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_config_file(self, config_data: dict) -> None:
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            raise ValueError(f"无法保存配置文件: {str(e)}")

    @property
    def debug_enabled(self) -> bool:
        self._load_env_file()
        return os.getenv("GROK_DEBUG", "false").lower() in ("true", "1", "yes")

    @property
    def retry_max_attempts(self) -> int:
        self._load_env_file()
        return int(os.getenv("GROK_RETRY_MAX_ATTEMPTS", "3"))

    @property
    def retry_multiplier(self) -> float:
        self._load_env_file()
        return float(os.getenv("GROK_RETRY_MULTIPLIER", "1"))

    @property
    def retry_max_wait(self) -> int:
        self._load_env_file()
        return int(os.getenv("GROK_RETRY_MAX_WAIT", "10"))

    @property
    def guda_base_url(self) -> str:
        self._load_env_file()
        return os.getenv("GUDA_BASE_URL", self._DEFAULT_GUDA_BASE_URL)

    @property
    def guda_api_key(self) -> str | None:
        self._load_env_file()
        return os.getenv("GUDA_API_KEY")

    @property
    def grok_api_url(self) -> str:
        self._load_env_file()
        url = os.getenv("GROK_API_URL")
        if not url:
            if self.guda_api_key:
                return f"{self.guda_base_url}/grok/v1"
            raise ValueError(f"Grok API URL 未配置！\n{self._SETUP_HINT}")
        parts = urlsplit(url)
        if parts.path in ("", "/"):
            return urlunsplit((parts.scheme, parts.netloc, "/v1", parts.query, parts.fragment))
        return url.rstrip("/")

    @property
    def grok_api_key(self) -> str:
        self._load_env_file()
        key = os.getenv("GROK_API_KEY") or self.guda_api_key
        if not key:
            raise ValueError(f"Grok API Key 未配置！\n{self._SETUP_HINT}")
        return key

    @property
    def tavily_enabled(self) -> bool:
        self._load_env_file()
        return os.getenv("TAVILY_ENABLED", "true").lower() in ("true", "1", "yes")

    @property
    def tavily_api_url(self) -> str:
        self._load_env_file()
        url = os.getenv("TAVILY_API_URL")
        if not url and self.guda_api_key:
            return f"{self.guda_base_url}/tavily"
        return url or "https://api.tavily.com"

    @property
    def tavily_api_key(self) -> str | None:
        self._load_env_file()
        return os.getenv("TAVILY_API_KEY") or self.guda_api_key

    @property
    def firecrawl_api_url(self) -> str:
        self._load_env_file()
        url = os.getenv("FIRECRAWL_API_URL")
        if not url and self.guda_api_key:
            return f"{self.guda_base_url}/firecrawl"
        return url or "https://api.firecrawl.dev/v2"

    @property
    def firecrawl_api_key(self) -> str | None:
        self._load_env_file()
        return os.getenv("FIRECRAWL_API_KEY") or self.guda_api_key

    @property
    def log_level(self) -> str:
        self._load_env_file()
        return os.getenv("GROK_LOG_LEVEL", "INFO").upper()

    @property
    def log_dir(self) -> Path:
        self._load_env_file()
        log_dir_str = os.getenv("GROK_LOG_DIR", "logs")
        log_dir = Path(log_dir_str)
        if log_dir.is_absolute():
            return log_dir

        home_log_dir = Path.home() / ".config" / "grok-search" / log_dir_str
        try:
            home_log_dir.mkdir(parents=True, exist_ok=True)
            return home_log_dir
        except OSError:
            pass

        cwd_log_dir = Path.cwd() / log_dir_str
        try:
            cwd_log_dir.mkdir(parents=True, exist_ok=True)
            return cwd_log_dir
        except OSError:
            pass

        tmp_log_dir = Path("/tmp") / "grok-search" / log_dir_str
        tmp_log_dir.mkdir(parents=True, exist_ok=True)
        return tmp_log_dir

    def _apply_model_suffix(self, model: str) -> str:
        try:
            url = self.grok_api_url
        except ValueError:
            return model
        if "openrouter" in url and ":online" not in model:
            return f"{model}:online"
        return model

    @property
    def grok_model(self) -> str:
        self._load_env_file()
        if self._cached_model is not None:
            return self._cached_model

        model = (
            os.getenv("GROK_MODEL")
            or self._load_config_file().get("model")
            or self._DEFAULT_MODEL
        )
        self._cached_model = self._apply_model_suffix(model)
        return self._cached_model

    def set_model(self, model: str) -> None:
        config_data = self._load_config_file()
        config_data["model"] = model
        self._save_config_file(config_data)
        self._cached_model = self._apply_model_suffix(model)

    @staticmethod
    def _mask_api_key(key: str) -> str:
        """脱敏显示 API Key，只显示前后各 4 个字符"""
        if not key or len(key) <= 8:
            return "***"
        return f"{key[:4]}{'*' * (len(key) - 8)}{key[-4:]}"

    def get_config_info(self) -> dict:
        """获取配置信息（API Key 已脱敏）"""
        try:
            api_url = self.grok_api_url
            api_key_raw = self.grok_api_key
            api_key_masked = self._mask_api_key(api_key_raw)
            config_status = "✅ 配置完整"
        except ValueError as e:
            api_url = "未配置"
            api_key_masked = "未配置"
            config_status = f"❌ 配置错误: {str(e)}"

        info = {
            "GUDA_BASE_URL": self.guda_base_url,
            "GUDA_API_KEY": self._mask_api_key(self.guda_api_key) if self.guda_api_key else "未配置",
            "GROK_API_URL": api_url,
            "GROK_API_KEY": api_key_masked,
            "GROK_MODEL": self.grok_model,
            "GROK_DEBUG": self.debug_enabled,
            "GROK_LOG_LEVEL": self.log_level,
            "GROK_LOG_DIR": str(self.log_dir),
            "TAVILY_API_URL": self.tavily_api_url,
            "TAVILY_ENABLED": self.tavily_enabled,
            "TAVILY_API_KEY": self._mask_api_key(self.tavily_api_key) if self.tavily_api_key else "未配置",
            "FIRECRAWL_API_URL": self.firecrawl_api_url,
            "FIRECRAWL_API_KEY": self._mask_api_key(self.firecrawl_api_key) if self.firecrawl_api_key else "未配置",
            "config_status": config_status,
        }
        return info

config = Config()
