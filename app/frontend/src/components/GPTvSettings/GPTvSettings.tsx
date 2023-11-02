import { useEffect, useState } from "react";
import { Stack, Checkbox, IDropdownOption, Dropdown } from "@fluentui/react";

import styles from "./GPTvSettings.module.css";
import { GPTVInput } from "../../api";

interface Props {
    gptvInputs: GPTVInput;
    useGptV: boolean;
    updateGPTvInputs: (input: GPTVInput) => void;
    updateUseGPTv: (useGPTv: boolean) => void;
}

export const GPTvSettings = ({ updateGPTvInputs, updateUseGPTv, useGptV, gptvInputs }: Props) => {
    const [useGPTv, setUseGPTV] = useState<boolean>(useGptV);
    const [vectorFieldOption, setVectorFieldOption] = useState<GPTVInput>(gptvInputs || GPTVInput.TextAndImages);

    const onUseGPTv = (_ev?: React.FormEvent<HTMLElement | HTMLInputElement>, checked?: boolean) => {
        updateUseGPTv(!!checked);
        setUseGPTV(!!checked);
    };

    const onSetGptVInput = (_ev: React.FormEvent<HTMLDivElement>, option?: IDropdownOption<GPTVInput> | undefined) => {
        if (option) {
            const data = option.key as GPTVInput;
            updateGPTvInputs(data || GPTVInput.TextAndImages);
            data && setVectorFieldOption(data);
        }
    };

    useEffect(() => {
        useGPTv && updateGPTvInputs(GPTVInput.TextAndImages);
    }, [useGPTv]);

    return (
        <Stack className={styles.container} tokens={{ childrenGap: 10 }}>
            <Checkbox checked={useGPTv} label="Use GPT-V" onChange={onUseGPTv} />
            {useGPTv && (
                <Dropdown
                    selectedKey={vectorFieldOption}
                    className={styles.oneshotSettingsSeparator}
                    label="GPTV Inputs"
                    options={[
                        {
                            key: GPTVInput.TextAndImages,
                            text: "Images and text from index"
                        },
                        { text: "Images only", key: GPTVInput.Images },
                        { text: "Text only", key: GPTVInput.Texts }
                    ]}
                    required
                    onChange={onSetGptVInput}
                />
            )}
        </Stack>
    );
};
