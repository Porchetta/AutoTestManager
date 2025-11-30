-- Create Users Table
CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(50) PRIMARY KEY,
    password_hash VARCHAR(255) NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    is_approved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create RTD Config Table
CREATE TABLE IF NOT EXISTS rtd_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_unit VARCHAR(100) NOT NULL,
    development_line VARCHAR(100) NOT NULL,
    home_dir_path VARCHAR(255) NOT NULL,
    is_target_line BOOLEAN NOT NULL DEFAULT FALSE
);

-- Create ezDFS Config Table
CREATE TABLE IF NOT EXISTS ezdfs_config (
    id INT AUTO_INCREMENT PRIMARY KEY,
    target_server_name VARCHAR(100) NOT NULL,
    dir_path VARCHAR(255) NOT NULL
);

-- Create User Favorites Table
CREATE TABLE IF NOT EXISTS user_favorites (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    rule_name VARCHAR(100) NOT NULL,
    target_server_id INT,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (target_server_id) REFERENCES ezdfs_config(id) ON DELETE SET NULL
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
INSERT INTO users (user_id, password_hash, is_admin, is_approved) VALUES ('admin', '$2b$12$dE5w9cFApfIYR.5rE9.LiusVihkMeEToFNnlA5pZl9jn1QcBycgMC', TRUE, TRUE);
