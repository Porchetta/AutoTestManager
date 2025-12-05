-- Create Users Table
CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(50) PRIMARY KEY,
    password_hash VARCHAR(255) NOT NULL,
    module_name VARCHAR(50) NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    is_approved BOOLEAN NOT NULL DEFAULT FALSE,
    created DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- TEST
-- Create RTD Config Table
CREATE TABLE IF NOT EXISTS rtd_config (
    line_name VARCHAR(50) PRIMARY KEY,
    line_id VARCHAR(50) NOT NULL,
    business_unit VARCHAR(50) NOT NULL,
    home_dir_path VARCHAR(255) NOT NULL,
    created DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modifier VARCHAR(50)
);

-- Create ezDFS Config Table
CREATE TABLE IF NOT EXISTS ezdfs_config (
    module_name VARCHAR(50) PRIMARY KEY,
    port_num VARCHAR(50) NOT NULL,
    home_dir_path VARCHAR(255) NOT NULL,
    created DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modifier VARCHAR(50)
);

-- Create User RTD Favorites Table
CREATE TABLE IF NOT EXISTS user_rtd_favorites (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    line_name VARCHAR(50),
    rule_name VARCHAR(50) NOT NULL,
    created DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (line_name) REFERENCES rtd_config(line_name) ON DELETE SET NULL
);

-- Create User ezDFS Favorites Table
CREATE TABLE IF NOT EXISTS user_ezfds_favorites (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    module_name VARCHAR(50),
    rule_name VARCHAR(50) NOT NULL,
    created DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (module_name) REFERENCES ezdfs_config(module_name) ON DELETE SET NULL
);

-- Create Test Results Table
CREATE TABLE IF NOT EXISTS test_results (
    task_id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    test_type VARCHAR(10) NOT NULL, -- 'RTD' or 'EZDFS'
    raw_result_path VARCHAR(255),
    summary_result_path VARCHAR(255),
    status VARCHAR(20) NOT NULL, -- 'PENDING', 'RUNNING', 'SUCCESS', 'FAILED'
    request_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    rtd_old_version VARCHAR(50),
    rtd_new_version VARCHAR(50),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Insert Default Admin User (Password: admin123)
-- Note: In production, use a proper hashed password. This is a placeholder hash for 'admin123' generated via bcrypt.
-- For this setup, we will handle hashing in the backend, but let's insert a known admin for initial access if needed.
-- Actually, it's safer to let the backend create the first admin or have a registration flow.
-- But for convenience, let's assume 'admin' / 'admin' for now.
-- Hash for 'admin': $2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxwKc.60rScphF.1k1.
INSERT INTO users (user_id, password_hash, module_name, is_admin, is_approved) VALUES ('admin', '$2b$12$dE5w9cFApfIYR.5rE9.LiusVihkMeEToFNnlA5pZl9jn1QcBycgMC', 'default', TRUE, TRUE);
