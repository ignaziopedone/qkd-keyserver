-- MySQL dump 10.13  Distrib 5.7.31, for Linux (x86_64)
--
-- Host: 172.16.0.2    Database: alice_data
-- ------------------------------------------------------
-- Server version	8.0.20

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

CREATE DATABASE IF NOT EXISTS alice_data;
USE alice_data;

--
-- Table structure for table `KmeExchangerData`
--

DROP TABLE IF EXISTS `KmeExchangerData`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `KmeExchangerData` (
  `KME_ID` varchar(255) NOT NULL,
  `key_handle` varchar(255) DEFAULT NULL,
  `key_ID` varchar(255) NOT NULL,
  `open` tinyint(1) NOT NULL,
  `module_ID` varchar(255) DEFAULT NULL,
  `module_address` varchar(255) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `KmeExchangerData`
--

LOCK TABLES `KmeExchangerData` WRITE;
/*!40000 ALTER TABLE `KmeExchangerData` DISABLE KEYS */;
/*!40000 ALTER TABLE `KmeExchangerData` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `bb`
--

DROP TABLE IF EXISTS `bb`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `bb` (
  `requestIP` varchar(255) NOT NULL,
  `complete` tinyint(1) DEFAULT NULL,
  `exchangedKey` text,
  `verified` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`requestIP`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `bb`
--

LOCK TABLES `bb` WRITE;
/*!40000 ALTER TABLE `bb` DISABLE KEYS */;
/*!40000 ALTER TABLE `bb` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `connectedSAE`
--

DROP TABLE IF EXISTS `connectedSAE`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `connectedSAE` (
  `SAE_ID` varchar(255) NOT NULL,
  `SAE_IP` varchar(255) NOT NULL,
  PRIMARY KEY (`SAE_ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `connectedSAE`
--

LOCK TABLES `connectedSAE` WRITE;
/*!40000 ALTER TABLE `connectedSAE` DISABLE KEYS */;
INSERT INTO `connectedSAE` VALUES ('SAE11223344','172.16.0.1');
/*!40000 ALTER TABLE `connectedSAE` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `currentExchange`
--

DROP TABLE IF EXISTS `currentExchange`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `currentExchange` (
  `destination` varchar(255) NOT NULL,
  `handle` varchar(255) NOT NULL,
  PRIMARY KEY (`destination`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;


--
-- Dumping data for table `currentExchange`
--

LOCK TABLES `currentExchange` WRITE;
/*!40000 ALTER TABLE `currentExchange` DISABLE KEYS */;
/*!40000 ALTER TABLE `currentExchange` ENABLE KEYS */;
UNLOCK TABLES;


--
-- Table structure for table `completedExchanges`
--

DROP TABLE IF EXISTS `completedExchanges`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `completedExchanges` (
  `destination` varchar(255) NOT NULL,
  `handle` varchar(255) NOT NULL,
  PRIMARY KEY (`destination`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;


--
-- Table structure for table `destinations`
--

DROP TABLE IF EXISTS `destinations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `destinations` (
  `SAE_ID` varchar(255) NOT NULL,
  `KME_ID` varchar(255) NOT NULL,
  PRIMARY KEY (`SAE_ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `destinations`
--

LOCK TABLES `destinations` WRITE;
/*!40000 ALTER TABLE `destinations` DISABLE KEYS */;
/*!40000 ALTER TABLE `destinations` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `exchangedKeys`
--

DROP TABLE IF EXISTS `exchangedKeys`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `exchangedKeys` (
  `KME_ID` varchar(255) NOT NULL,
  `KME_IP` varchar(255) NOT NULL,
  `KME_PORT` int NOT NULL,
  `AUTH_KEY_ID` varchar(255) NOT NULL,
  `KEY_IDs` text,
  `KEY_COUNT` int DEFAULT '0',
  `DEF_KEY_SIZE` int DEFAULT '128',
  `MAX_KEY_COUNT` int DEFAULT '500',
  `MAX_KEY_PER_REQUEST` int DEFAULT '3',
  `MAX_KEY_SIZE` int DEFAULT '1024',
  `MIN_KEY_SIZE` int DEFAULT '8',
  `MAX_SAE_ID_COUNT` int DEFAULT '0',
  PRIMARY KEY (`KME_ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `exchangedKeys`
--

LOCK TABLES `exchangedKeys` WRITE;
/*!40000 ALTER TABLE `exchangedKeys` DISABLE KEYS */;
INSERT INTO `exchangedKeys` VALUES ('KME55667788','10.0.2.15',4000,'68e3f6d0-d273-11ea-aada-ffeca5cd1502',NULL,0,128,500,3,128,8,0);
/*!40000 ALTER TABLE `exchangedKeys` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `handles`
--

DROP TABLE IF EXISTS `handles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `handles` (
  `handle` varchar(255) NOT NULL,
  `destination` varchar(255) DEFAULT NULL,
  `timeout` int DEFAULT NULL,
  `length` int DEFAULT NULL,
  `synchronized` tinyint(1) NOT NULL,
  `newKey` tinyint(1) NOT NULL,
  `currentKeyNo` int DEFAULT 0,
  `stop` tinyint(1) DEFAULT 0,
  PRIMARY KEY (`handle`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `handles`
--

LOCK TABLES `handles` WRITE;
/*!40000 ALTER TABLE `handles` DISABLE KEYS */;
/*!40000 ALTER TABLE `handles` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `log`
--

DROP TABLE IF EXISTS `log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `log` (
  `timestamp` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `level` int NOT NULL,
  `message` text NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `log`
--

LOCK TABLES `log` WRITE;
/*!40000 ALTER TABLE `log` DISABLE KEYS */;
/*!40000 ALTER TABLE `log` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `qkdmodules`
--

DROP TABLE IF EXISTS `qkdmodules`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `qkdmodules` (
  `moduleID` varchar(255) NOT NULL,
  `module` varchar(255) NOT NULL,
  `protocol` varchar(255) DEFAULT NULL,
  `moduleIP` varchar(255) NOT NULL,
  `max_key_count` int DEFAULT 0,
  PRIMARY KEY (`moduleID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `reservedKeys`
--

DROP TABLE IF EXISTS `reservedKeys`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `reservedKeys` (
  `KME_ID` varchar(255) NOT NULL,
  `SAEKeys` text,
  PRIMARY KEY (`KME_ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `reservedKeys`
--

LOCK TABLES `reservedKeys` WRITE;
/*!40000 ALTER TABLE `reservedKeys` DISABLE KEYS */;
/*!40000 ALTER TABLE `reservedKeys` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2020-08-06 21:32:45
