-- =====================================================================
--  FundTrail — MySQL setup script
--  (The original setup.sql shipped EMPTY; this is the real one.)
--
--  How to run (you will be prompted for the MySQL root password):
--      mysql -u root -p < setup.sql
--
--  SECURITY NOTE:
--    * Do NOT hard-code the real password in this committed file.
--    * Replace 'CHANGE_ME_STRONG_PASSWORD' below before running, OR
--      set the password interactively with ALTER USER afterwards.
-- =====================================================================

-- 1) Application database (utf8mb4 so names/addresses in any language work)
CREATE DATABASE IF NOT EXISTS fundtrail
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

-- 2) Dedicated least-privilege application user.
--    The app logs in as THIS user, never as root.
CREATE USER IF NOT EXISTS 'fundtrail'@'localhost'
    IDENTIFIED BY 'CHANGE_ME_STRONG_PASSWORD';

-- 3) Grant only what the app needs, and only on its own database.
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP, REFERENCES
    ON fundtrail.* TO 'fundtrail'@'localhost';

FLUSH PRIVILEGES;

-- =====================================================================
--  After running this script:
--   1. Put the matching URL in your .env:
--        DATABASE_URL=mysql+pymysql://fundtrail:THE_PASSWORD@localhost:3306/fundtrail
--   2. Create the tables (either run the app once, or use migrations):
--        flask db upgrade
--   3. Create the login users (admin / officer / viewer):
--        python scripts/create_user.py
-- =====================================================================
