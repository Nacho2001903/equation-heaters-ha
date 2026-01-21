"""Support for Equation Climate."""

from __future__ import annotations

from abc import ABC

from equationsdk.device import EquationDevice

from homeassistant.components.climate import (
    PRESET_COMFORT,
    PRESET_ECO,
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CMD_SET_HVAC_MODE,
    CMD_SET_PRESET,
    CMD_SET_TEMP,
    DOMAIN,
    LOGGER,
    PRESET_EQUATION_ICE,
    RADIATOR_MODE_AUTO,
    RADIATOR_MODE_MANUAL,
    RADIATOR_PRESET_COMFORT,
    RADIATOR_PRESET_ECO,
    RADIATOR_PRESET_ICE,
    RADIATOR_TEMP_MAX,
    RADIATOR_TEMP_MIN,
    RADIATOR_TEMP_STEP,
)
from .coordinator import EquationDataUpdateCoordinator
from .equation_entity import EquationRadiatorEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the radiator climate entity from the config entry."""
    coordinator: EquationDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    coordinator.add_entities_for_seen_keys(
        async_add_entities, [EquationHaClimate], "climate"
    )


class EquationHaClimate(EquationRadiatorEntity, ClimateEntity, ABC):
    """Climate entity."""

    def __init__(
        self,
        radiator: EquationDevice,
        coordinator: EquationDataUpdateCoordinator,
    ) -> None:
        """Init the Climate entity."""
        super().__init__(
            coordinator, radiator, name=radiator.name, unique_id=radiator.id
        )

        self.entity_description = ClimateEntityDescription(
            key="radiator",
            name=radiator.name,
        )

    @property
    def icon(self) -> str | None:
        return "mdi:radiator"

    @property
    def temperature_unit(self) -> str:
        return UnitOfTemperature.CELSIUS

    @property
    def target_temperature(self) -> float:
        if self._radiator.mode == RADIATOR_MODE_MANUAL:
            if self._radiator.preset == RADIATOR_PRESET_ECO:
                return self._radiator.eco_temp
            if self._radiator.preset == RADIATOR_PRESET_COMFORT:
                return self._radiator.comfort_temp
            if self._radiator.preset == RADIATOR_PRESET_ICE:
                return self._radiator.ice_temp

        return self._radiator.temp

    @property
    def current_temperature(self) -> float:
        return self._radiator.temp_probe

    @property
    def max_temp(self) -> float:
        if self._radiator.user_mode_supported and self._radiator.user_mode:
            return self._radiator.um_max_temp
        return RADIATOR_TEMP_MAX

    @property
    def min_temp(self) -> float:
        if self._radiator.user_mode_supported and self._radiator.user_mode:
            return self._radiator.um_min_temp
        return RADIATOR_TEMP_MIN

    @property
    def target_temperature_high(self) -> float:
        return self.max_temp

    @property
    def target_temperature_low(self) -> float:
        return self.min_temp

    # 🔥 AQUÍ ESTÁ LA CLAVE
    @property
    def supported_features(self) -> ClimateEntityFeature:
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

    @property
    def target_temperature_step(self) -> float | None:
        return RADIATOR_TEMP_STEP

    @property
    def hvac_modes(self) -> list[str]:
        return [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]

    @property
    def preset_modes(self) -> list[str]:
        return [PRESET_COMFORT, PRESET_ECO, PRESET_EQUATION_ICE]

    @property
    def hvac_mode(self) -> str:
        if not self._radiator.power:
            return HVACMode.OFF

        if self._radiator.mode == RADIATOR_MODE_AUTO:
            return HVACMode.AUTO

        return HVACMode.HEAT

    @property
    def hvac_action(self) -> str:
        if (
            self._radiator.mode == RADIATOR_MODE_AUTO
            and self._radiator.preset == HVACMode.OFF
        ):
            return HVACAction.IDLE

        if not self._radiator.power:
            return HVACAction.OFF

        return HVACAction.HEATING

    @property
    def preset_mode(self) -> str | None:
        if self._radiator.preset == RADIATOR_PRESET_ECO:
            return PRESET_ECO
        if self._radiator.preset == RADIATOR_PRESET_COMFORT:
            return PRESET_COMFORT
        if self._radiator.preset == RADIATOR_PRESET_ICE:
            return PRESET_EQUATION_ICE

        return None

    async def async_set_temperature(self, **kwargs):
        target_temperature = float(kwargs["temperature"])

        if not await self.device_manager.send_command(
            self._radiator, CMD_SET_TEMP, target_temperature
        ):
            raise HomeAssistantError(
                f"Failed to set temperature for {self._radiator.name}"
            )

        await self._signal_thermostat_update()

    async def async_set_hvac_mode(self, hvac_mode):
        LOGGER.debug("Setting HVAC mode to %s", hvac_mode)

        if not await self.device_manager.send_command(
            self._radiator, CMD_SET_HVAC_MODE, hvac_mode
        ):
            raise HomeAssistantError(
                f"Failed to set HVAC mode for {self._radiator.name}"
            )

        await self._signal_thermostat_update()

    async def async_set_preset_mode(self, preset_mode):
        LOGGER.debug("Setting preset mode: %s", preset_mode)

        if not await self.device_manager.send_command(
            self._radiator, CMD_SET_PRESET, preset_mode
        ):
            raise HomeAssistantError(
                f"Failed to set preset mode for {self._radiator.name}"
            )

        await self._signal_thermostat_update()

    # ✅ NUEVO: TURN ON / OFF
    async def async_turn_on(self):
        """Turn the radiator on."""
        LOGGER.debug("Turning ON radiator %s", self._radiator.name)
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self):
        """Turn the radiator off."""
        LOGGER.debug("Turning OFF radiator %s", self._radiator.name)
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def _signal_thermostat_update(self):
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()
