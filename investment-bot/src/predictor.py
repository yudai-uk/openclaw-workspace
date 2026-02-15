"""
機械学習予測モジュール
過去のシグナルと結果から学習して、より精度の高い勝率を予測する
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
import sqlite3
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
import joblib

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import trading_config, db_config

logger = logging.getLogger(__name__)


class MLPredictor:
    """機械学習勝率予測クラス（改善版）"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or db_config.DB_PATH
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False

        # モデルファイルパス
        self.model_path = Path(__file__).parent.parent / "data" / "ml_model.pkl"
        self.scaler_path = Path(__file__).parent.parent / "data" / "scaler.pkl"

        # 既存のモデルがあればロード
        self._load_model()

    def _load_model(self):
        """既存のモデルをロード"""
        try:
            if self.model_path.exists() and self.scaler_path.exists():
                self.model = joblib.load(self.model_path)
                self.scaler = joblib.load(self.scaler_path)
                self.is_trained = True
                logger.info("既存の機械学習モデルをロードしました")
        except Exception as e:
            logger.warning(f"モデルロード失敗: {e}")
            self.model = VotingClassifier([
                ('rf', RandomForestClassifier(n_estimators=100, random_state=42)),
                ('gb', GradientBoostingClassifier(n_estimators=100, random_state=42)),
            ])
            self.is_trained = False

    def train_model(self) -> bool:
        """
        過去データでモデルを学習

        Returns:
            成功時True
        """
        logger.info("機械学習モデル学習開始")

        try:
            # データベースから過去のシグナルと結果を取得
            signals_df = self._load_signals()

            if len(signals_df) < 20:
                logger.warning("学習データが不足しています（20件以上必要）")
                return False

            # 特徴量とターゲットを分離
            X, y = self._prepare_features(signals_df)

            if len(X) == 0:
                logger.warning("有効な学習データがありません")
                return False

            # データの標準化
            X_scaled = self.scaler.fit_transform(X)

            # モデル学習
            self.model.fit(X_scaled, y)
            self.is_trained = True

            # モデル保存
            self._save_model()

            # モデル評価
            self._evaluate_model(X_scaled, y)

            logger.info(f"モデル学習完了（{len(X)}件のデータ）")
            return True

        except Exception as e:
            logger.error(f"モデル学習エラー: {e}")
            return False

    def predict_win_rate(self, signal: Dict[str, Any]) -> float:
        """
        シグナルから勝率を予測

        Args:
            signal: シグナルデータ

        Returns:
            予測勝率 (0.0 ~ 1.0)
        """
        # モデルが学習済みなら使用
        if self.is_trained:
            try:
                return self._predict_with_model(signal)
            except Exception as e:
                logger.warning(f"モデル予測エラー: {e}、フォールバックを使用")

        # フォールバック：統計的予測
        return self._predict_with_statistics(signal)

    def _predict_with_model(self, signal: Dict[str, Any]) -> float:
        """
        機械学習モデルで勝率を予測

        Args:
            signal: シグナルデータ

        Returns:
            予測勝率
        """
        # 特徴量抽出
        features = self._extract_features(signal)
        features_scaled = self.scaler.transform([features])

        # 確率予測
        proba = self.model.predict_proba(features_scaled)[0]

        # 正クラス（勝ち）の確率を返す
        return proba[1]

    def _predict_with_statistics(self, signal: Dict[str, Any]) -> float:
        """
        統計的手法で勝率を予測（フォールバック）

        Args:
            signal: シグナルデータ

        Returns:
            予測勝率
        """
        # シグナルスコアから勝率を予測
        signal_score = signal.get("signal_score", 0)

        # アンサンブルシグナルを考慮
        ensemble_signal = signal.get("ensemble_signal", "neutral")
        if ensemble_signal in ["strong_buy", "buy"]:
            signal_score += 2
        elif ensemble_signal in ["strong_sell", "sell"]:
            signal_score -= 2

        # テクニカルシグナルを考慮
        technical = signal.get("technical", {})
        tech_signal = technical.get("signal", "neutral")
        if tech_signal in ["strong_buy", "buy"]:
            signal_score += 2
        elif tech_signal in ["strong_sell", "sell"]:
            signal_score -= 2

        # シグナルスコアを勝率にマッピング
        base_rate = 0.50
        rate_range = 0.40  # ±40%

        win_rate = base_rate + (signal_score / 10) * rate_range
        return max(0.10, min(0.90, win_rate))

    def _load_signals(self) -> pd.DataFrame:
        """
        データベースからシグナルを読み込み

        Returns:
            シグナルデータフレーム
        """
        try:
            conn = sqlite3.connect(self.db_path)
            query = """
            SELECT
                signal_score,
                overall_sentiment,
                rsi,
                macd_histogram,
                ma5_slope,
                ma10_slope,
                ma20_slope,
                ma50_slope,
                ma5_pct,
                ma10_pct,
                ma20_pct,
                ma50_pct,
                change_pct,
                ensemble_signal,
                result  -- 1: 勝ち, 0: 負け
            FROM trades
            WHERE result IS NOT NULL
            ORDER BY timestamp DESC
            """

            df = pd.read_sql_query(query, conn)
            conn.close()

            logger.info(f"{len(df)}件のシグナルを読み込みました")
            return df

        except Exception as e:
            logger.error(f"シグナル読み込みエラー: {e}")
            return pd.DataFrame()

    def _prepare_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        特徴量とターゲットを準備

        Args:
            df: シグナルデータフレーム

        Returns:
            (特徴量, ターゲット)
        """
        # アンサンブルシグナルを数値化
        ensemble_signal_map = {"neutral": 0, "buy": 1, "sell": -1, "strong_buy": 2, "strong_sell": -2}
        df["ensemble_signal_num"] = df["ensemble_signal"].map(ensemble_signal_map).fillna(0)

        # 欠損値を処理
        df = df.fillna(0)

        # 特徴量カラム
        feature_columns = [
            "signal_score",
            "overall_sentiment",
            "ensemble_signal_num",
            "rsi",
            "macd_histogram",
            "ma5_slope",
            "ma10_slope",
            "ma20_slope",
            "ma50_slope",
            "ma5_pct",
            "ma10_pct",
            "ma20_pct",
            "ma50_pct",
            "change_pct",
        ]

        X = df[feature_columns].values
        y = df["result"].values

        return X, y

    def _extract_features(self, signal: Dict[str, Any]) -> List[float]:
        """
        シグナルから特徴量を抽出

        Args:
            signal: シグナルデータ

        Returns:
            特徴量リスト
        """
        technical = signal.get("technical", {})

        # アンサンブルシグナルを数値化
        ensemble_signal_map = {"neutral": 0, "buy": 1, "sell": -1, "strong_buy": 2, "strong_sell": -2}
        ensemble_signal_num = ensemble_signal_map.get(signal.get("ensemble_signal", "neutral"), 0)

        features = [
            signal.get("signal_score", 0),
            signal.get("overall_sentiment", 0),
            ensemble_signal_num,
            technical.get("rsi", 50),
            technical.get("macd_histogram", 0),
            technical.get("ma5_slope", 0),
            technical.get("ma10_slope", 0),
            technical.get("ma20_slope", 0),
            technical.get("ma50_slope", 0),
            technical.get("ma5_pct", 0),
            technical.get("ma10_pct", 0),
            technical.get("ma20_pct", 0),
            technical.get("ma50_pct", 0),
            signal.get("change_pct", 0),
        ]

        return features

    def _save_model(self):
        """モデルを保存"""
        try:
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(self.model, self.model_path)
            joblib.dump(self.scaler, self.scaler_path)
            logger.info("機械学習モデルを保存しました")
        except Exception as e:
            logger.error(f"モデル保存エラー: {e}")

    def _evaluate_model(self, X: np.ndarray, y: np.ndarray):
        """
        モデルを評価

        Args:
            X: 特徴量
            y: ターゲット
        """
        try:
            # 学習データでの正解率
            train_accuracy = self.model.score(X, y)
            logger.info(f"学習データ正解率: {train_accuracy:.2%}")

            # クロスバリデーション
            scores = cross_val_score(self.model, X, y, cv=5)
            logger.info(f"クロスバリデーション正解率: {scores.mean():.2%} (±{scores.std() * 2:.2%})")

        except Exception as e:
            logger.warning(f"モデル評価エラー: {e}")

    def record_result(self, signal: Dict[str, Any], result: int):
        """
        取引結果を記録

        Args:
            signal: シグナルデータ
            result: 結果 (1: 勝ち, 0: 負け)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # テーブルがなければ作成
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT,
                symbol TEXT,
                side TEXT,
                quantity REAL,
                price REAL,
                order_type TEXT,
                status TEXT,
                timestamp TEXT,
                profit_loss REAL,
                signal_score REAL,
                overall_sentiment REAL,
                rsi REAL,
                macd_histogram REAL,
                ma5_slope REAL,
                ma10_slope REAL,
                ma20_slope REAL,
                ma50_slope REAL,
                ma5_pct REAL,
                ma10_pct REAL,
                ma20_pct REAL,
                ma50_pct REAL,
                change_pct REAL,
                ensemble_signal TEXT,
                result INTEGER
            )
            """)

            # 結果記録
            technical = signal.get("technical", {})

            cursor.execute("""
            INSERT INTO trades (
                order_id, symbol, side, quantity, price, order_type, status, timestamp, profit_loss,
                signal_score, overall_sentiment, rsi, macd_histogram,
                ma5_slope, ma10_slope, ma20_slope, ma50_slope,
                ma5_pct, ma10_pct, ma20_pct, ma50_pct, change_pct, ensemble_signal, result
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal.get("order_id", ""),
                signal.get("symbol"),
                signal.get("action"),
                signal.get("quantity", 0),
                signal.get("current_price", 0),
                "MARKET",
                signal.get("status", "dry_run"),
                signal.get("timestamp"),
                signal.get("profit_loss", 0),
                signal.get("signal_score", 0),
                signal.get("overall_sentiment", 0),
                technical.get("rsi", 50),
                technical.get("macd_histogram", 0),
                technical.get("ma5_slope", 0),
                technical.get("ma10_slope", 0),
                technical.get("ma20_slope", 0),
                technical.get("ma50_slope", 0),
                technical.get("ma5_pct", 0),
                technical.get("ma10_pct", 0),
                technical.get("ma20_pct", 0),
                technical.get("ma50_pct", 0),
                signal.get("change_pct", 0),
                signal.get("ensemble_signal", "neutral"),
                result,
            ))

            conn.commit()
            conn.close()

            logger.info(f"取引結果を記録しました: {signal.get('symbol')} (result={result})")

            # 定期的にモデルを再学習（例：20回ごと）
            self._check_retrain()

        except Exception as e:
            logger.error(f"結果記録エラー: {e}")

    def _check_retrain(self):
        """定期的にモデルを再学習"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 記録数を確認
            cursor.execute("SELECT COUNT(*) FROM trades")
            count = cursor.fetchone()[0]

            conn.close()

            # 20回ごとに再学習
            if count > 0 and count % 20 == 0:
                logger.info("機械学習モデルを再学習します")
                self.train_model()

        except Exception as e:
            logger.warning(f"再学習チェックエラー: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        統計情報を取得

        Returns:
            統計情報の辞書
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 総取引数
            cursor.execute("SELECT COUNT(*) FROM trades")
            total_trades = cursor.fetchone()[0]

            # 勝利数
            cursor.execute("SELECT COUNT(*) FROM trades WHERE result = 1")
            wins = cursor.fetchone()[0]

            # 勝率
            win_rate = wins / total_trades if total_trades > 0 else 0

            # 平均利益
            cursor.execute("SELECT AVG(profit_loss) FROM trades WHERE profit_loss IS NOT NULL")
            avg_profit = cursor.fetchone()[0] or 0

            # 総利益
            cursor.execute("SELECT SUM(profit_loss) FROM trades WHERE profit_loss IS NOT NULL")
            total_profit = cursor.fetchone()[0] or 0

            # 最大ドローダウン
            cursor.execute("SELECT MIN(profit_loss) FROM trades WHERE profit_loss IS NOT NULL")
            max_loss = cursor.fetchone()[0] or 0

            conn.close()

            return {
                "total_trades": total_trades,
                "wins": wins,
                "losses": total_trades - wins,
                "win_rate": win_rate,
                "avg_profit": avg_profit,
                "total_profit": total_profit,
                "max_loss": max_loss,
            }

        except Exception as e:
            logger.error(f"統計情報取得エラー: {e}")
            return {}


if __name__ == "__main__":
    # テスト実行
    import logging
    logging.basicConfig(level=logging.INFO)

    predictor = MLPredictor()

    # モデル学習
    predictor.train_model()

    # 統計情報表示
    stats = predictor.get_statistics()
    print(f"\n統計情報:")
    print(f"  総取引数: {stats.get('total_trades', 0)}")
    print(f"  勝率: {stats.get('win_rate', 0):.2%}")
    print(f"  総利益: {stats.get('total_profit', 0):.2f}")
