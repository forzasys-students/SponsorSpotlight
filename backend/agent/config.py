import configparser
import os

class ConfigManager:
    """
    A singleton class to manage the application's configuration.
    It ensures that the config is loaded only once.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """Loads configuration from config.ini and sets instance variables."""
        print("DEBUG: Initializing ConfigManager and loading configuration...")
        config = configparser.ConfigParser()
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config.ini')

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"config.ini not found at {config_path}")
            
        config.read(config_path)

        # Load and clean API key
        api_key = config.get('openai', 'api_key', fallback=None)
        if not api_key or "YOUR_GPT4_API_KEY_HERE" in api_key:
            raise ValueError("API key not set in config.ini")
        self.api_key = api_key.strip().strip('"').strip("'")
        
        # Load model and clean it
        model = config.get('openai', 'model', fallback='gpt-4o')
        self.model = model.strip().strip('"').strip("'")
        
        # Load Instagram config
        self.instagram_access_token = config.get('instagram', 'access_token', fallback='').strip().strip('"').strip("'")
        self.instagram_user_id = config.get('instagram', 'user_id', fallback='').strip().strip('"').strip("'")

        # Load FTP config
        self.ftp_hostname = config.get('ftp', 'hostname', fallback='').strip().strip('"').strip("'")
        self.ftp_username = config.get('ftp', 'username', fallback='').strip().strip('"').strip("'")
        self.ftp_password = config.get('ftp', 'password', fallback='').strip().strip('"').strip("'")
        self.ftp_public_url_base = config.get('ftp', 'public_url_base', fallback='').strip().strip('"').strip("'")

        print(f"DEBUG: Config loaded successfully. Model: {self.model}, Key ends in: ...{self.api_key[-4:]}")

    def get_api_key(self):
        """Returns the cleaned OpenAI API key."""
        return self.api_key

    def get_model(self):
        """Returns the OpenAI model name."""
        return self.model

    def get_instagram_credentials(self):
        """Returns Instagram access token and user ID."""
        return self.instagram_access_token, self.instagram_user_id

    def get_ftp_credentials(self):
        """Returns FTP credentials."""
        return self.ftp_hostname, self.ftp_username, self.ftp_password, self.ftp_public_url_base

# Create a single, globally accessible instance of the manager
config_manager = ConfigManager()
