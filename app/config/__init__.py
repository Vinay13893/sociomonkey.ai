from .settings import DevelopmentConfig, ProductionConfig, TestingConfig, get_config_name

config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
}
