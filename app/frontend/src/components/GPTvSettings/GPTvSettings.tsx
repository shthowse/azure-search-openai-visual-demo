import { useEffect, useState } from "react";
import { Stack, Checkbox, IDropdownOption, Dropdown } from "@fluentui/react";

import styles from "./GPTvSettings.module.css";
import { GPTVInput } from "../../api";

interface Props {
    updateGPTvInputs: (input: GPTVInput) => void;
    updateUseGPTv: (useGPTv: boolean) => void;
}

export const GPTvSettings = ({ updateGPTvInputs, updateUseGPTv }: Props) => {
    const [useGPTv, setUseGPTV] = useState<boolean>(false);
    const [vectorFieldOption, setVectorFieldOption] = useState<GPTVInput>(GPTVInput.TextAndImages);

    const onUseGPTv = (_ev?: React.FormEvent<HTMLElement | HTMLInputElement>, checked?: boolean) => {
        updateUseGPTv(!!checked);
        setUseGPTV(!!checked);
    };

    const onSetGptVInput = (_ev: React.FormEvent<HTMLDivElement>, option?: IDropdownOption<GPTVInput> | undefined) => {
        if (option) {
            updateGPTvInputs(option.data || GPTVInput.TextAndImages);
            option.data && setVectorFieldOption(option.data);
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
                    defaultSelectedKey={GPTVInput.TextAndImages}
                    className={styles.oneshotSettingsSeparator}
                    label="GPTV Inputs"
                    options={[
                        {
                            key: GPTVInput.TextAndImages,
                            text: "Images and text from index",
                            data: GPTVInput.TextAndImages
                        },
                        { key: "images", text: "Images only", data: GPTVInput.Images },
                        { key: "text", text: "Text only", data: GPTVInput.Texts }
                    ]}
                    selectedKey={vectorFieldOption}
                    required
                    onChange={onSetGptVInput}
                />
            )}
        </Stack>
    );
};
