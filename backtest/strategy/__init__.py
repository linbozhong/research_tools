from .turtle_b_strategy import TurtleBStrategy
from .turtle_c_strategy import TurtleCStrategy
from .turtle_d_strategy import TurtleDStrategy
from .turtle_e_strategy import TurtleEStrategy

from .turtle_rsi_strategy import TurtleRsiFilterStrategy
from .turtle_fluid_strategy import TurtleFluidSizeStrategy

from .boll_channel_strategy import BollChannelStrategy
from .boll_ma_strategy import BollMaStrategy
from .boll_ma_rsi_strategy import BollMaRsiStrategy
from .boll_ma_fluid_strategy import BollFluidStrategy

from .double_ma_strategy import DoubleMaStrategy
from .double_ma_rsi_strategy import DoubleMaRsiStrategy
from .double_ma_std_strategy import DoubleMaStdStrategy
from .double_ma_atr_strategy import DoubleMaAtrStrategy
from .double_ma_atr_b_strategy import DoubleMaAtrBStrategy
from .double_ma_exit_ma_strategy import DoubleMaExitMaStrategy
from .double_ma_exit_ma_rein_strategy import DoubleMaExitMaReinStrategy
from .double_ma_exit_atr_rein_strategy import DoubleMaExitAtrReinStrategy

from .tri_ma_strategy import TriMaStrategy

from .macd_strategy import MacdStrategy
from .macd_exit_atr_rein_strategy import MacdExitAtrReinStrategy
from .macd_m_in_hist_out_rein_strategy import MacdMinHoutReinStrategy

from .atr_rsi_strategy import AtrRsiStrategy


strategy_class_map = {
    'turtle': TurtleBStrategy,
    'turtle_inverse_trade': TurtleCStrategy,
    'turtle_exit_ma': TurtleDStrategy,
    'turtle_entry_following_stop': TurtleEStrategy,
    'turtle_rsi_filter': TurtleRsiFilterStrategy,
    'turtle_fluid_size': TurtleFluidSizeStrategy,
    'boll': BollChannelStrategy,
    'boll_exit_ma': BollMaStrategy,
    'boll_ma_rsi': BollMaRsiStrategy,
    'boll_fluid': BollFluidStrategy,
    'double_ma': DoubleMaStrategy,
    'double_ma_rsi': DoubleMaRsiStrategy,
    'double_ma_std': DoubleMaStdStrategy,
    'double_ma_atr': DoubleMaAtrStrategy,
    'double_ma_atr_plus_ma': DoubleMaAtrBStrategy,
    'double_ma_exit_ma': DoubleMaExitMaStrategy,
    'double_ma_exit_ma_rein': DoubleMaExitMaReinStrategy,
    'double_ma_exit_atr_rein': DoubleMaExitAtrReinStrategy,
    'tri_ma': TriMaStrategy,
    'macd': MacdStrategy,
    'macd_exit_atr_rein': MacdExitAtrReinStrategy,
    'macd_m_in_hist_out_rein': MacdMinHoutReinStrategy,
    'atr_rsi': AtrRsiStrategy
}