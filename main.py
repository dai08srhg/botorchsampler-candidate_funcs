import optuna
import os
import numpy as np
import polars as pl
from enum import Enum
from tqdm import tqdm
from test_functions.single_objective import Hartmann6, StyblinskiTang, FiveWellPotentioal, Hartmann6Cat2, SumOfSquares, SumOfDiffSquares
from candidates_funcs.single_objective_candidates_func import (
    ei_gammma_prior,
    ei_dim_scaled_prior,
    logei_gammma_prior,
    logei_dim_scaled_prior,
    lcb,
    ei_saas,
    experimental,
    thompson_sampling
)


TargetFunction = Hartmann6 | StyblinskiTang | FiveWellPotentioal | Hartmann6Cat2 | SumOfSquares


class SamplerName(str, Enum):
    """最適化バージョン."""

    TPE = 'TPE'
    EIGammaPrior = 'EI GammaPrior'
    EIDimScaledPrior = 'EI DimScaledPrior'
    EISaas = 'EI Saas'
    LogEIGammaPrior = 'LogEI GammaPrior'
    LogEIDimScaledPrior = 'LogEI DimScaledPrior'
    LCB = 'LCB'
    ThompsonSampling = 'thompson sampling'
    EXPERIMENTAL = 'experimental'


class Optimizer:
    """最適化クラス."""

    def __init__(self, sampler_name: SamplerName):
        if sampler_name == SamplerName.TPE:
            self.sampler = optuna.samplers.TPESampler()
        elif sampler_name == SamplerName.LCB:
            self.sampler = optuna.integration.BoTorchSampler(candidates_func=lcb)
        elif sampler_name == SamplerName.EIGammaPrior:
            self.sampler = optuna.integration.BoTorchSampler(candidates_func=ei_gammma_prior)
        elif sampler_name == SamplerName.EIDimScaledPrior:
            self.sampler = optuna.integration.BoTorchSampler(candidates_func=ei_dim_scaled_prior)
        elif sampler_name == SamplerName.EISaas:
            self.sampler = optuna.integration.BoTorchSampler(candidates_func=ei_saas)
        elif sampler_name == SamplerName.LogEIGammaPrior:
            self.sampler = optuna.integration.BoTorchSampler(candidates_func=logei_gammma_prior)
        elif sampler_name == SamplerName.LogEIDimScaledPrior:
            self.sampler = optuna.integration.BoTorchSampler(candidates_func=logei_dim_scaled_prior)
        elif sampler_name == SamplerName.ThompsonSampling:
            self.sampler = optuna.integration.BoTorchSampler(candidates_func=thompson_sampling)
        elif sampler_name == SamplerName.EXPERIMENTAL:
            self.sampler = optuna.integration.BoTorchSampler(candidates_func=experimental)
        else:
            pass

    def _set_samples(self, Xs: np.ndarray, ys: np.ndarray, distributions: dict):
        """studyに観測データを登録.

        ※ Tell_and_Askのインターフェースを利用.

        Args:
            Xs (np.ndarray): shape=(n, x_dim).
            ys (np.ndarray): shape=(n, y_dim).
            distributions (Dict[str, optuna.distributions]): 探索空間

        """
        features = list(distributions.keys())
        for X, y in zip(Xs, ys):
            params = {}
            for feature, x in zip(features, X):
                params[feature] = x
            trial = optuna.trial.create_trial(params=params, distributions=distributions, value=y[0])
            self.study.add_trial(trial)

    def create_study(self, direction):
        self.study = optuna.create_study(direction=direction, sampler=self.sampler)

    def get_candidate(self, Xs: np.ndarray, ys: np.ndarray, distributions: dict):
        """候補点を取得.

        Args:
            Xs (np.ndarray): shape=(n, x_dim)
            ys (np.ndarray): shape=(n, y_dim)
            distributions (Dict[str, optuna.distributions]): 探索空間

        """
        self._set_samples(Xs, ys, distributions)
        trial = self.study.ask()
        new_X = []
        for feature, dist in distributions.items():
            if type(dist) is optuna.distributions.FloatDistribution:
                new_X.append(trial.suggest_float(feature, dist.low, dist.high))
            elif type(dist) is optuna.distributions.CategoricalDistribution:
                new_X.append(trial.suggest_categorical(feature, dist.choices))
        new_X = np.array(new_X)
        return new_X.reshape(1, new_X.shape[0])


def run_optimization(
    func: TargetFunction,
    direction: str,
    X_init: np.ndarray,
    y_init: np.ndarray,
    sampler_name: SamplerName,
    iters: int = 100,
):
    """探索を実行."""
    sampler = Optimizer(sampler_name)
    Xs = X_init.copy()
    ys = y_init.copy()

    distributions = func.distributions
    for _ in tqdm(range(iters)):
        sampler.create_study(direction)
        new_X = sampler.get_candidate(Xs, ys, distributions)
        new_y = func.f(new_X)
        Xs = np.concatenate([Xs, new_X])
        ys = np.concatenate([ys, new_y])
    return ys


def get_target_function(exp_name: str) -> TargetFunction:
    """実験名に応じて, 目的関数を返す."""
    if exp_name == 'StyblinskiTang8':
        return StyblinskiTang(dim=8)
    elif exp_name == 'StyblinskiTang40':
        return StyblinskiTang(dim=40)
    elif exp_name == 'Hartmann6':
        return Hartmann6()
    elif exp_name == 'Hartmann6Cat2':
        return Hartmann6Cat2()
    elif exp_name == 'FiveWellPotentioal':
        return FiveWellPotentioal()
    elif exp_name == 'SumOfDiffSquares40':
        return SumOfDiffSquares(dim=40)
    elif exp_name == 'SumOfSquares40':
        return SumOfSquares(dim=40)


def main():
    """実験実行."""
    #### 実験設定 #####
    exp_name = 'SumOfSquares40'

    direction = 'minimize'
    EXP_NUM = 3  # 実験回数
    SERCH_NUM = 100  # 観測回数
    INIT_NUM = 10  # 初期点の数
    # use_methods = [SamplerName.EXPERIMENTAL]
    use_methods = [SamplerName.EIGammaPrior, SamplerName.EIDimScaledPrior, SamplerName.LogEIGammaPrior, SamplerName.LogEIDimScaledPrior]
    ##################

    print(f'Run experiment: {exp_name}')
    os.makedirs(f'exp_result/{exp_name}', exist_ok=True)

    # 目的関数取得
    f = get_target_function(exp_name)

    for j in range(1, EXP_NUM + 1):
        print(f'Start trial:{j}')
        serch_fs = {}

        # 初期点ランダムに10点
        X_init = f.random_x()
        y_init = f.f(X_init)
        for _ in range(INIT_NUM - 1):
            X = f.random_x()
            y = f.f(X)
            X_init = np.concatenate([X_init, X])
            y_init = np.concatenate([y_init, y])

        # ランダム探索
        ys_random = y_init.copy()
        for _ in range(SERCH_NUM):
            new_y = f.f(f.random_x())
            ys_random = np.concatenate([ys_random, new_y])
        serch_fs['Random'] = ys_random.squeeze()

        # 各手法で探索
        for method in use_methods:
            print(f'Start optimization using {method.value}')
            ys = run_optimization(f, direction, X_init, y_init, method, SERCH_NUM)
            serch_fs[method.value] = ys.squeeze()

        # 探索結果を格納
        df = pl.DataFrame(serch_fs)
        df.write_csv(f'exp_result/{exp_name}/run_{j}.csv')


if __name__ == '__main__':
    optuna.logging.disable_default_handler()
    main()
