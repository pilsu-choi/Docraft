// const {Logger}            = require('common/logger');
const { Logger } = require('/usr/src/app/dist/apps/extn/libs/common/src/logger');

// const pluginUtil  = require("./pluginUtil.js");

/**
 * 2024.09.23 루나
 * 조건 1. 추출 된 결과가 없는 경우(data.values === []) label 을 null 로 정의한다.
 */
exports.setResultFormat = function setResultFormat(values, keyObj, arrtcd, category) {

  let resultArr = [];
  let extrtId = 1;
  let lvlNo = 1;

  // 진료비영수증의 표데이터 추출레벨번호 처리를 위해 작성
  let chartLvlNo = 0;
  let rlChartYN = false;  // TODO 한 문서에 relativeLabelsInfo, relativeValueKeywordInfo 둘 다 사용하는 경우가 생기면 추가 작업 필요
  let rLabelYn = false; //세부내역서 하단 표(계, 끝처리조정금액, 합계)
  // 영역 추출 결과
  let areaSearchResult = values?.filter((value) => value?.ruleName === 'AreaSearch');

  // values 에서 불필요한 값 제거
  values = values?.filter((value) => value?.ruleName !== 'CollectTabularData' && value?.ruleName !== 'CollectStrikeThroughData' && value?.ruleName !== 'AreaSearch');
  // 스키마에는 정의되어 있으나, 항목리스트.json 에는 정의되지 않은 경우에 대한 처리 (항목리스트.json 에 추가처리여부 정의)
  // 항목리스트 추출항목에 정의 된 항목이 없는 경우
  // Logger.log("11",values)
  let afterItmYN = keyObj["추가처리여부"];
  // Logger.log(keyObj["추출항목"]?.length)
  if (afterItmYN === "Y" || keyObj["추출항목"]?.length < 1) {
    values?.filter((value) => keyObj["추출항목"]?.indexOf(value?.name) < 0)
      .forEach((value) => {
        // 추출항목 마지막에 추가
        keyObj["추출항목"].push(value?.name);
      });

    // Logger.log(keyObj["표추출항목"])
    // 표대상항목 중 항목리스트 표추출항목에 정의 된 항목이 없는 경우
    values?.filter((value) => keyObj["표대상항목"]?.indexOf(value?.name) >= 0)
      .forEach((value) => {
        value?.data?.forEach((data) => {
          data?.values
            .filter((v) => { return v?.relativeLabelsInfo?.length > 0 ? true : false; })
            .forEach((v) => {
              if (v?.relativeLabelsInfo?.length > 0) {
                rlChartYN = true;
              }
            });
        });
      });

    keyObj["추출항목"] = keyObj["추출항목"]?.filter((key) => key !== '');

  }

  // 후처리항목이 있는 경우 표추출항목의 순서 변경되도록 설정
  keyObj["표추출항목"] = keyObj["표추출항목"]?.sort((a, b) => {
    return keyObj["후처리항목"]?.indexOf(a) - keyObj["후처리항목"]?.indexOf(b);
  });

  //세부내역서 하단 표에 필요
  const tmpArr = [];

  // resultArr push 로직 시작
  if (typeof values !== 'undefined' && values?.length > 0) {


    keyObj["추출항목"]?.forEach((key, i) => {
      let itmValue = values?.filter((value) => value?.name === key && value?.data?.length > 0);
      if (itmValue?.length < 1) {
        resultArr.push(resultFormat(keyObj, extrtId, lvlNo, 0, null, key, null, null, [], [], 1.0, "N", null));
      } else {
        itmValue?.forEach((value) => {
          // 여러 번 출력 된 경우 status 가 0 아래 값 제거 후 label 합치기
          if (value?.data?.length > 1) {
            value.data = value?.data?.filter((data) => data?.status >= 0 && !value?.selectRuleType?.includes("Check"));
          }

          // data 가 여러 개인 경우 (이미지 상 동일 키워드가 여러 번 나오는 경우)
          // 조건. 첫 번째 값만 가져오는 것으로 처리
          const skipNames = ["표데이터", "계"];

          if (value?.data?.length > 1 && !skipNames.includes(value.name)) {
            value.data = [value?.data[0]];
          }
          // [2025-03-11] value?.data에 값이 없는 경우 처리
          if (value?.data?.length === 0) {
            resultArr.push(resultFormat(keyObj, extrtId, lvlNo, 0, null, key, null, null, [], [], 1.0, "N", null));
          }
          // Logger.log("333",extrtId)2
          value?.data?.forEach((data) => {
            // 표데이터
            if (keyObj["표대상항목"]?.indexOf(value?.name) >= 0) {
              // relativeLabelsInfo 를 사용하는 경우 (ex. 진료비영수증)
              if (rlChartYN) {
                if (keyObj["표대상항목"]?.indexOf(value?.name) === 0) chartLvlNo = lvlNo;
                else lvlNo = chartLvlNo;

                keyObj["표추출항목"]?.forEach((k) => {
                  let chartValue = data?.values?.filter((v) => {
                    let tmpLabel = '';
                    v?.relativeLabelsInfo?.forEach((rl) => {
                      tmpLabel += rl?.label

                    });
                    if (k === tmpLabel) {
                      return true;
                    }
                  });
                  if (chartValue?.length > 0) {
                    // 표추출항목의 values 가 여러 개인 경우
                    // 숫자인 경우 더해서 보여지도록 설정
                    if (chartValue?.length > 1) {
                      if (k !== '입원료') Logger.log('🚨🚨🚨🚨🚨🚨🚨 표추출항목이 여러개인 경우', value?.name, '\t', k); // JSON.stringify(chartValue, null, 1)

                      let numLabel = 0;
                      chartValue?.forEach((o) => {
                        let tmpLabel = o?.label?.replace(/[^0-9]/gi, '');
                        tmpLabel = isNaN(tmpLabel) ? 0 : Number(tmpLabel);

                        numLabel += tmpLabel;
                      });
                      if (numLabel > 0) {
                        chartValue[0].label = numLabel;
                        chartValue[0].relativeLabelsInfo[0].label = k;
                      }

                      chartValue = [chartValue[0]];
                    }

                    chartValue?.forEach((v) => {
                      v?.relativeLabelsInfo?.forEach((rl, rlIdx) => {
                        resultArr.push(resultFormat(keyObj, extrtId, lvlNo, (keyObj["표타이틀"]?.indexOf(value?.name) + 1), null, k, rl?.label, v?.label, rl?.coordinates, v?.coordinates, v?.confidence, "Y", value?.name));
                        extrtId++;
                        lvlNo++;
                      });
                    });
                  } else {
                    resultArr.push(resultFormat(keyObj, extrtId, lvlNo, (keyObj["표타이틀"]?.indexOf(value?.name) + 1), null, k, k, null, [], [], 1.0, "N", value?.name));
                    extrtId++;
                    lvlNo++;
                  }
                });
              }
              // relativeValueKeywordInfo 를 사용하는 경우 (ex. 진료비세부내역서)
              else {
                // Logger.log("##333##", resultArr?.filter((data) => data?.img_extc_itnm))
                let chartTitle = keyObj["표타이틀"];
                if (chartTitle.length < 1 && keyObj[`표타이틀_` + key]?.length > 0) {
                  chartTitle = keyObj[`표타이틀_` + key];
                }
                // TODO 작업 중
                if (afterItmYN === "Y") {
                  // Logger.log('⭐⭐⭐ ', key, '\t', chartTitle);
                }

                data?.values?.forEach((v) => {
                  // v?.relativeValueInfo?.forEach((r)=>{
                  //   Logger.log(r.keyLabels[0]," ===> ", r.label)
                  // })
                  let extrtSno = 0;
                  let valueSno = 0;

                  if (afterItmYN === "Y") {
                    chartTitle?.forEach((tv, ti) => {
                      extrtSno++;
                      const match = v?.relativeValueInfo?.find((rv) => {
                        return rv?.keyLabels?.join('_') === tv;
                      });
                      // 추출 정의 항목과 추출된 key가 같은 경우 정의된 룰대로 push
                      if (match) {
                        // Logger.log("⭐⭐⭐",v?.relativeValueInfo[valueSno]?.keyLabels?.join(''), v?.relativeValueInfo[valueSno]?.label, extrtId)
                        resultArr.push(resultFormat(keyObj, extrtId, lvlNo, extrtSno, null, v?.relativeValueInfo[valueSno]?.keyLabels?.join(''), v?.relativeValueInfo[valueSno]?.keyLabels?.join(''), v?.relativeValueInfo[valueSno]?.label, v?.relativeValueInfo[valueSno]?.coordinates, v?.coordinates, v?.relativeValueInfo[valueSno]?.confidence, "Y", value?.name));
                        valueSno++;
                        // 추출 정의 항목과 추출된 key가 같지 않은 경우
                      } else {
                        // 메인 key로 뽑은 경우
                        if (tv === data?.keyLabels?.join('')) {
                          resultArr.push(resultFormat(keyObj, extrtId, lvlNo, extrtSno, null, tv, tv, v?.label, v?.coordinates, v?.coordinates, v?.confidence, "Y", value?.name));
                          // 추출되지 않은 경우 'N'으로 PUSH
                        } else {
                          resultArr.push(resultFormat(keyObj, extrtId, lvlNo, extrtSno, null, tv, tv, null, [], [], 1.0, "N", value?.name));
                        }
                      }
                    });
                    // Logger.log("##555##", resultArr?.filter((data) => data?.img_extc_itnm === '일수'))
                  } else {
                    // relativeValueKeywordInfo 로 정의 된 룰에 의한 추출 값
                    v?.relativeValueInfo?.forEach((rv) => {
                      extrtSno++;
                      resultArr.push(resultFormat(keyObj, extrtId, lvlNo, extrtSno, null, rv?.keyLabels?.join(''), rv?.keyLabels?.join(''), rv?.label, rv?.coordinates, v?.coordinates, rv?.confidence, "Y", value?.name));
                    });
                  }

                  extrtId++;
                  lvlNo++;
                });
              }
            }
            // 추출 된 결과가 없는 경우 
            else if (data?.values?.length < 1) {
              resultArr.push(resultFormat(keyObj, extrtId, lvlNo, 0, null, value?.name, data?.keyLabels?.join(''), null, data?.values[0]?.coordinates, [], data?.values[0]?.confidence, "N", null));
            }
            // 한 가지 항목만 추출 된 경우
            else if (data?.values?.length > 0 && data?.values[0]?.relativeLabelsInfo?.length < 1 && data?.values[0]?.relativeValueInfo?.length < 1) {
              let label = '';
              if (data?.values?.length > 1) data?.values?.forEach((v) => label += v?.label);
              else label = data?.values[0]?.label;

              resultArr.push(resultFormat(keyObj, extrtId, lvlNo, 0, null, value?.name, data?.keyLabels?.join(''), label, data?.values[0]?.coordinates, [], data?.values[0]?.confidence, "Y", null));
            }
            // [2025-03-11] 체크박스인 경우
            else if (data?.values?.length > 0 && (value?.ruleName === 'SearchByCheckbox' || value?.selectRuleType === 'SearchByCheckbox')) {
              data.values = data?.values?.filter((v) => v?.checked === 1);
              let label = '';
              data?.values?.forEach((v, vIdx) => {
                label += v?.label;
                // if(vIdx < data?.values?.length-1) label += '|';
                if (vIdx < data?.values?.length - 1) label += '';
              });

              resultArr.push(resultFormat(keyObj, extrtId, lvlNo, 0, null, value?.name, data?.keyLabels, label, data?.values[0]?.coordinates, [], data?.values[0]?.confidence, "Y", null));
            }
            //세부내역서 하단 표(계, 끝처리조정금액, 합계)
            // else if (value?.name === "계") {
            //   // Logger.log("After: ",value.data)
            //   data?.values.forEach((v) => {
            //     // Logger.log("🍙", data?.keyLabels?.[0], "===>", v.label,"===> ",v?.relativeLabelsInfo)
            //     let tmpObj = {}
            //     tmpObj = {
            //       img_extc_itnm: data?.keyLabels?.[0],
            //       lvl_no: 1,
            //       extc_itm_no: extrtId,
            //       hgrk_extc_itm_no: 0,
            //       extc_rst_cont01: v?.label,
            //       extc_rst_cont09: '',
            //       extc_rst_cont10: '',
            //       extc_itm_tpvl: '',
            //       self_rlbtr_vl: v.confidence,
            //       extrt_raw_itm_nm: '',
            //       extrtYn: "Y",
            //       chartNm: v?.relativeLabelsInfo?.[0]?.label,
            //       extrtSno: 0,
            //       itm_val_coord_val: v?.coordinates
            //       // extrtItmNm: "계_" + v?.relativeLabelsInfo[0]?.label,
            //     }
            //     tmpArr.push(tmpObj);
            //   });
            //   // extrtId =extrtId+1
            // }
            else if (value?.name === "끝처리조정금액" || value?.name === "합계" || value?.name==="계") {
              // Logger.log("After: ",value.data[0]?.values)
              data?.values.forEach((v) => {
                // Logger.log("333",value?.name, v.label, v?.relativeLabelsInfo?.[0]?.label, data?.keyLabels?.[0])
                const tmpObj = {
                  img_extc_itnm: data?.keyLabels?.[0], //합계
                  lvl_no: 1,
                  extc_itm_no: extrtId,
                  hgrk_extc_itm_no: 0,
                  extc_rst_cont01: v?.label,
                  extc_rst_cont09: '',
                  extc_rst_cont10: '',
                  extc_itm_tpvl: null,
                  self_rlbtr_vl: v.confidence,
                  extrt_raw_itm_nm: '',
                  extrtYn: "Y",
                  chartNm: v?.relativeLabelsInfo?.[0]?.label, //총액 공단, 본인, 전액본인
                  // chartNm: "표데이터",
                  extrtSno: 0,
                  itm_val_coord_val: v?.coordinates
                }
                tmpArr.push(tmpObj);
              });
              // extrtId = extrtId+1
            }
            // else if (value?.name === "소계") {
            //   data?.values?.forEach((v) => {
            //     // Logger.log(v)
            //     const tmpObj = {
            //       img_extc_itnm: data?.keyLabels?.[0],
            //       lvl_no: 1,
            //       extc_itm_no: extrtId,
            //       hgrk_extc_itm_no: 0,
            //       extc_rst_cont01: v?.label,
            //       extc_rst_cont09: '',
            //       extc_rst_cont10: '',
            //       extc_itm_tpvl: '',
            //       self_rlbtr_vl: v.confidence,
            //       extrt_raw_itm_nm: '',
            //       extrtYn: "Y",
            //       chartNm: v?.relativeLabelsInfo?.[0]?.label,
            //       extrtSno: 0,
            //       itm_val_coord_val: v?.coordinates
            //     }
            //     tmpArr.push(tmpObj);
            //   });
            // }
            else {
              Logger.log('🚨🚨🚨🚨🚨🚨🚨 케이스 테스트 필요 \t', value?.name);
              data?.values.forEach((v) => {
                if (value?.name.split("_")[1] == v?.relativeLabelsInfo[0]?.label) {
                  label = v?.relativeLabelsInfo[0]?.label;
                  // Logger.log(label)
                }
              })
              if (data?.values?.length > 0) {
                let label = '';
                if (data?.values?.length > 1)
                  data?.values?.forEach((v) => label += v?.label);
                else
                  label = data?.values[0]?.label;
                resultArr.push(resultFormat(keyObj, extrtId, lvlNo, 0, null, value?.name, data?.keyLabels?.join(''), label, data?.values[0]?.coordinates, [], data?.values[0]?.confidence, "Y", null));
              } else {
                resultArr.push(resultFormat(keyObj, extrtId, lvlNo, 0, null, key, null, null, [], [], 1.0, "N", null));
                // resultArr.push(resultFormat(keyObj, extrtId, lvlNo, extrtSno, null, value?.name, data?.keyLabels?.join(''), label, data?.values[0]?.coordinates, [], data?.values[0]?.confidence, label === null ? "N" : "Y", null));
              }

              // resultArr.push(resultFormat(keyObj, extrtId, lvlNo, 0, null, key, null, null, [], [], 1.0, "N", null));
              // resultArr.push(resultFormat(keyObj, extrtId, lvlNo, extrtSno, null, value?.name, data?.keyLabels?.join(''), label, data?.values[0]?.coordinates, [], data?.values[0]?.confidence, label === null ? "N" : "Y", null));
            }
            // Logger.log("111111111111111111111111111111111",resultArr)


          });
        });
      }
      if (keyObj["표대상항목"]?.indexOf(key) < 0) {
        extrtId++;
        lvlNo++;
      }
    });

    // Logger.log("*******==================================*******")

    resultArr = resultArr.filter(
      item => item.img_extc_itnm !== "합계"
    );
    tmpArr.forEach(tmp => {
      // resultArr에서 extrtItmNm(추출항목명)이 chartNm(표데이터 표 이름)과 같은 객체를 찾음
      const match = resultArr.find(res => res.img_extc_itnm === tmp.chartNm);
      // if (match) {
      //   tmp.extrtSno = match.extrtSno; // 덮어쓰기
      // }
    });

    const tmpArr2 = []
    const handledExtrtIds = new Set();

    tmpArr.forEach(tmp => {
      if(tmp.img_extc_itnm !== '합계') return;
      if (!handledExtrtIds.has(`${tmp.extc_itm_no}_${tmp.img_extc_itnm}`)) {
        handledExtrtIds.add(`${tmp.extc_itm_no}_${tmp.img_extc_itnm}`);
        // console.log("22222222222222",tmp.extc_itm_no, tmp.img_extc_itnm)

        tmpArr2.push({
          ...tmp,
          img_extc_itnm: '항목',
          extc_rst_seq: 0,
          extc_rst_cont01: "합계"
        });
        
        // tmpArr2.push({
        //   img_extc_itnm: '항목',
        //   lvl_no: 1,
        //   extc_itm_no: tmp.extc_itm_no,
        //   hgrk_extc_itm_no: 0,
        //   extc_rst_cont01: tmp.img_extc_itnm,
        //   extc_rst_cont09: '',
        //   extc_rst_cont10: '',
        //   self_rlbtr_vl: 1,
        //   extrt_raw_itm_nm: '',
        //   extrtYn: 'Y',
        //   chartNm: '표데이터',
        //   extrtSno: 0,
        //   itm_val_coord_val: []
        // });
      }
    });
    tmpArr.push(...tmpArr2)

    tmpArr.sort((a,b) => {
      if (Number(a.extc_itm_no) !== Number(b.extc_itm_no)) {
        return Number(a.extc_itm_no) - Number(b.extc_itm_no);
      }
      
      if (a.img_extc_itnm === '항목' && b.img_extc_itnm === '합계') return -1;
      if (a.img_extc_itnm === '합계' && b.img_extc_itnm === '항목') return -1;

      return ;
    });
    tmpArr.forEach((tmp, key) => {
      // Logger.log("444444",tmp)
      if (tmp.img_extc_itnm === "합계" && tmp.chartNm === undefined) {
        // Logger.log(`chartNm을 못가져와서 합계 추출 안됨`)
        tmp.chartNm = "표데이터";
      }
      if (tmp.chartNm && tmp.img_extc_itnm != "항목") {
        if (tmp.img_extc_itnm == "계") tmp.img_extc_itnm = "계_" + tmp.chartNm;
        if (tmp.img_extc_itnm == "합계") tmp.img_extc_itnm = "급여_" + tmp.chartNm;
        else if (tmp.img_extc_itnm == "소계") tmp.img_extc_itnm = "소계_" + tmp.chartNm;
      }
      tmp.chartNm = "표데이터";
    });
    // console.log(tmpArr)
    // keyObj["표타이틀"] 기준으로 tmpArr 정리
    const groupedByExtrtId = tmpArr.reduce((acc, item) => {
      if (!acc[item.extc_itm_no]) acc[item.extc_itm_no] = [];
      acc[item.extc_itm_no].push(item);
      return acc;
    }, {});

    Object.entries(groupedByExtrtId).forEach(([extrtIdStr, items]) => {
      const extrtId = Number(extrtIdStr);
      const extrtLvlNo = items[0]?.lvlNo;

      const normKey = (s) =>
        (s ?? "").toString().replace(/\s+/g, "").replace(/[::]/g, "").trim();
      const itemMap = new Map();
      // 기존 항목을 map에 저장 (key = extrtItmNm)
      items.forEach(item => {
        const key = normKey(item.img_extc_itnm);
        if (key) itemMap.set(key, item);
      });
      
      const newTmpArr = [];

      // 표타이틀 순서대로 정렬 및 누락 항목 추가
      // 표타이틀 >> 후처리항목으로 변경 /1.14 (합계_, 계_ 추출)
      let orderIdx = 0;

      const itemRow = itemMap.get(normKey("항목"));
      if(itemRow) {
        itemRow.extrtSno = ++orderIdx;
        newTmpArr.push(itemRow)
      }
      keyObj["후처리항목"].forEach((rawTitle, idx) => {
        const titleKey = normKey(rawTitle);
        // Logger.log(rawTitle, titleKey)
        const isSum = titleKey.startsWith("급여_"); 
        const isTot = titleKey.startsWith("계_");
        const isSub = titleKey.startsWith("소계_");

        const item = itemMap.get(titleKey);
        // console.log("!!",item)
        //매칭된 기존 항목이 잇을 때
        if (item) {
          const val = (item.extc_rst_cont01 ?? "").toString().trim();

          if ((isSum || isTot || isSub) && val === "") return;

          item.extrtSno = ++orderIdx;
          newTmpArr.push(item);
          // Logger.log("1111", item.extrtSno)
          return;
        }

        // 매칭이 없을 때, 합계_ or 계_ 는 생성 자체를 하지 않음
        if (isSum || isTot || isSub) return;
        //일반 항목만 누락 시 생성
        newTmpArr.push({
          img_extc_itnm: titleKey,
          extc_itm_no: "",
          lvlNo,
          extc_rst_cont01: "",
          extc_rst_cont09: '',
          extc_rst_cont10: '',
          self_rlbtr_vl: 1,
          extrtYn: "N",
          chartNm: "표데이터",
          extrt_raw_itm_nm: '',
          extrtSno: ++orderIdx,
        });
      });
      resultArr.push(...newTmpArr);
    });
    // Logger.log("1111",resultArr)
    // 공통 포멧 변경
    resultArr.forEach((obj) => {
      // 날짜 포멧 변경
      if (typeof keyObj["날짜데이터"] !== 'undefined' && keyObj["날짜데이터"]?.length > 0 && keyObj["날짜데이터"]?.indexOf(obj?.img_extc_itnm) >= 0) {
        obj.extc_rst_cont01 = this.setDateFormat(obj?.extc_rst_cont01);
      }
    });

  }

  /////////////////////////////////////////0223 추가
  //급여_ 붙은거 extc_itm_no 재정리
  const isPayroll = (x) => (x?.img_extc_itnm ?? "").toString().startsWith("급여_");
  const isNonPayrollTotal = (x) => (x?.img_extc_itnm ?? "").toString() === "급여_비급여";
  const isSumItem = (x) => 
  (x?.img_extc_itnm ?? "").toString() === "항목" &&
  (x?.extc_rst_cont01 ?? "").toString() === "합계";
  
  //1) 분리
  const payrollItems = resultArr.filter(isPayroll) || [];
  const nonPayrollItems = resultArr.filter(isNonPayrollTotal) || [];
  const sumItemRows = resultArr.filter(isSumItem) || [];
  const otherItems = resultArr.filter((x) => !isPayroll(x) && !isNonPayrollTotal(x) && !isSumItem(x)) || [];

  // console.log(payrollItems)
  //2) max
  let maxId = otherItems.reduce((m, x) => {
    const n = Number(x?.extc_itm_no);
    return Number.isFinite(n) ? Math.max(m, n) : m;
  }, 0);

  //3) 급여_ 모드 같은 extc_itm_no
  const payrollExtcId = maxId + 1;
  let seq = 1;

  for (let i = 0; i < payrollItems.length; i ++) {
    payrollItems[i].extc_itm_no = payrollExtcId;
    payrollItems[i].extc_rst_seq = seq++;
  }

  const nonPayrollExtcId = payrollExtcId;
  
  for (let i = 0; i < nonPayrollItems.length; i ++) {
    nonPayrollItems[i].extc_itm_no = nonPayrollExtcId;
    nonPayrollItems[i].extc_rst_seq = 0;
  }

  for (let i = 0; i < sumItemRows.length; i ++) {
    sumItemRows[i].extc_itm_no = payrollExtcId;
    sumItemRows[i].extc_rst_seq = 0;
  }
  
  // console.log('444444',JSON.stringify(resultArr))
  return resultArr;
}
/**
 * 날짜 포멧 셋팅
 * @param {*} cntnt 
 * @returns YYYYMMDD
 */
exports.setDateFormat = function setDateFormat(cntnt) {
  let nowYear = String(new Date().getFullYear());
  // 1. 숫자 ./-년월일 외 제거
  cntnt = cntnt.replace(/[^0-9년월일\\.\\/\\~\\-]/g, '');

  if (cntnt === '') return '';

  // 2. .년월일-/ 기준으로 split
  let dateArr = cntnt.split(/년|월|일|\.|\/|\-|\~/);

  // Logger.log("ORIGIN : ", cntnt, cntnt.length, dateArr.length)

  // Logger.log("🍩🍩", cntnt,"=> ",dateArr, "====>",dateArr.length, "==>", cntnt.length)
  let year, month, day, resultDate, year2, month2, day2 = '';
  // 3. 경우에 따라 로직 구현
  // case 1. 추출 된 데이터가 YYYYMMDD 인 경우
  if (cntnt?.length == 10) { //기본 형식 ex. 2024-01-12 OR 10자리 이상은 숫자만 그대로 추출
    return dateArr?.join('')
  }
  else if (cntnt?.length === 9) {
    // Logger.log("1️⃣. 9자리 경우 1️⃣")
    if (dateArr.length === 1 || dateArr.length === 2) { //ex.20240105n , 20241-111, 202412-11...
      resultDate = dateArr?.join('');
    }
    else if (dateArr.length == 3) {
      if (dateArr[0].length === 4) { //ex.2024-1-12, 2024-12-2
        year = dateArr[0];
        if (dateArr[1] < 13 && dateArr[1] >= 1) {
          month = setMmddFormat(dateArr[1]);
          day = setMmddFormat(dateArr[2])
        }
        else { //ex. 2024-111-, 2024--111
          month = dateArr[1];
          day = dateArr[2];
        }
        resultDate = year + month + day;
      } else {
        resultDate = dateArr?.join('');
      }
    }
    return resultDate;
  }
  else if ((cntnt?.length === 8)) {
    // Logger.log("1️⃣. 8자리 경우 1️⃣", cntnt)
    if (dateArr.length === 1) { //기본 8자리 (ex.20240105)
      return dateArr?.join('');
    }
    else if (dateArr.length == 2) { //ex. 2024-303, 2024-105(1월인지10월인지 구분 안돼서 그대로)
      year = dateArr[0];
      if (year.length === 4) {
        if (dateArr[1].charAt(0) != 1) { //2024-303
          month = setMmddFormat(dateArr[1].substr(0, 1));
          day = dateArr[1].substr(1,)
        }
        else { //2024-105
          month = dateArr[1];
        }
      }
      else if (year.length > 4) { //ex. 20241-05 , 202412-5
        month = setMmddFormat(year.substr(4, 2));
        year = year.substr(0, 4);
        day = setMmddFormat(dateArr[1]);
      }
      else year = dateArr?.join('')
      return year + month + day;
    }
    else if (dateArr.length === 3) { //ex. 2024-1-5, 24-11-05 
      if (dateArr[0].length === 4) {
        year = dateArr[0];
        month = setMmddFormat(dateArr[1]);
        day = setMmddFormat(dateArr[2]);
      }
      else if (dateArr[0].length === 2) { //ex. 20241-15
        year = setYearFormat(dateArr[0]);
        month = setMmddFormat(dateArr[1]);
        day = setMmddFormat(dateArr[2]);
      }
      else if (dateArr[0].length === 5) {  //ex. 20241-5-, 20241-0-
        year = dateArr[0].substr(0, 4);
        month = dateArr[0].substr(4, 1)
        if (dateArr[1] > 2) {
          month = setMmddFormat(month)
        } else month = month;
        day = dateArr[1];
      }
      else {
        year = dateArr[0];
        month = setMmddFormat(dateArr[1]);
        day = setMmddFormat(dateArr[2]);
      }
      return year + month + day;
    }
    else {
      return dateArr?.join('');
    }
  }
  else if (cntnt?.length === 7) {
    // Logger.log("2️⃣. 7자리 경우 2️⃣")
    if (dateArr.length === 1) { //ex. 2024105, 2024305, 2024015
      year = dateArr[0].substr(0, 4);
      let md = dateArr[0].substr(4,);
      if ((md.substr(0, 1) == 0)) { //ex.2024015 
        month = md.substr(0, 2);
        day = setMmddFormat(md.substr(2,));
      }
      else if ((md.substr(0, 1) == 1) && (md.substr(1, 1) < 3)) { //ex. 2024105 (1월인지 10월인지 모르기 때문에 그대로 추출)
        month = md;
      }
      else if ((md.substr(0, 1) > 1)) { //ex.2024305
        month = setMmddFormat(md.substr(0, 1));
        day = md.substr(1,);
      }
      return year + month + day;
    }
    else if (dateArr.length == 2) { // 오인식 (ex. 20241-05, 20241-5, 202411-05,202411-5...)
      if (dateArr[0].length == 2) { //ex. 24-0103
        year = setYearFormat(dateArr[0])
        if (dateArr[1].length == 4) {
          month = dateArr[1].substr(0, 2);
          day = dateArr[1].substr(2, 2);
        }
        else {
          resultDate = dateArr?.join('');
        }
        resultDate = year + month + day;
      }
      else if (dateArr[0]?.length === 4) { //ex.2024-15, 2401-15 구분이 명확하지 못함으로 그대로 추출
        year = dateArr[0].substr(0, 2)
        month = dateArr[0].substr(2, 2)
        day = dateArr[1]
        if ((month >= 1 && month <= 12)) { //가운데 두자리가 1~12일 경우만 YYMMDD
          year = setYearFormat(year);
          month = setMmddFormat(month);
          day = setMmddFormat(day);
        }
        else {
          if (day > 12) { //가운데 두자리가 12 초과 일 경우는 그대로 
            year = dateArr[0];
            month = setMmddFormat(day.substr(0, 1))
            day = setMmddFormat(day.substr(1,));
          }
        }
        resultDate = year + month + day;
      }
      else if (dateArr[0].length == 5) { //ex. 20241-2, 20241-5, 20243-6...
        year = dateArr[0].substr(0, 4);
        month = setMmddFormat(dateArr[0].substr(4,));
        day = setMmddFormat(dateArr[1].substr(0, 2));
        resultDate = year + month + day;
      }
      else resultDate = dateArr?.join('')
      return resultDate
    }
  }
  else if (cntnt?.length === 6) {
    // Logger.log("3️⃣. 6자리 경우 3️⃣")
    if (dateArr.length === 1) { //ex. 240103,202411 -가운데 두자리가 1~12일 경우만 YYMMDD, 이외는 그대로 추출
      year = cntnt.substr(0, 2)
      month = cntnt.substr(2, 2)
      day = cntnt.substr(4, 2)
      if ((month >= 1 && month <= 12)) {
        year = setYearFormat(year);
        month = setMmddFormat(month);
        day = setMmddFormat(day);
      }
      return year + month + day;
    }
    else if (dateArr.length === 2) {
      if (dateArr[0].length === 2) { //ex.24-115, 24-015, 24-615...
        year = setYearFormat(dateArr[0])
        if (dateArr[1].charAt(0) == 0) { //ex. 24-015
          month = dateArr[1].substr(0, 2);
          day = setMmddFormat(dateArr[1].substr(2,));
        }
        else if (dateArr[1].charAt(0) == 1) {
          month = dateArr[1];
        }
        else {
          month = setMmddFormat(dateArr[1].substr(0, 1));
          day = dateArr[1].substr(1,);
        }
      }
      else if (dateArr[0].length === 4) { //ex. 2024-3,  2401-5
        year = dateArr[0].substr(0, 2);
        month = dateArr[0].substr(2, 2)
        day = setMmddFormat(dateArr[1])
        if ((month >= 1 && month <= 12)) { //2401-5
          year = setYearFormat(year);
          month = setMmddFormat(month);
        } else { //2024-3
          year = dateArr[0];
          month = setMmddFormat(dateArr[1])
          day = ''
        }
      }
      else { //ex. 241-15, 20241-
        year = dateArr?.join('');
        month = '';
        day = '';
      }
      resultDate = year + month + day;
      return resultDate
    }
    else if (dateArr.length === 3) {
      if (dateArr[0].length == 2) { //ex. 24-1-1, 24-51-, 24--51
        year = setYearFormat(dateArr[0]);
        month = setMmddFormat(dateArr[1]);
        day = setMmddFormat(dateArr[2]);
      }
      else { //ex. 2024--
        year = dateArr?.join('');
        month = '';
        day = '';
      }
      resultDate = year + month + day;
      return resultDate
    }
  }
  // else if(cntnt?.lenght==12){
  //   let firstDate, secondDate;
  //   if(dateArr.length ==1){
  //     firstDate = dateArr[0].substr(0,6);
  //     secondDate =dateArr[0].substr(6,6);
  //   }
  //   Logger.log(firstDate,"////",secondDate)
  // }
  else if (cntnt?.length === 13 && dateArr.length == 2) {
    // Logger.log(" 13자리 경우 ")
    if (dateArr[0].length == 6) {
      year = cntnt.substr(0, 2)
      month = cntnt.substr(2, 2)
      day = cntnt.substr(4, 2)
      if ((month >= 1 && month <= 12)) {
        year = setYearFormat(year);
        month = setMmddFormat(month);
        day = setMmddFormat(day);
      }
      dateArr[0] = year + month + day
    }
    if (dateArr[1].length == 6) {
      year = cntnt.substr(0, 2)
      month = cntnt.substr(2, 2)
      day = cntnt.substr(4, 2)
      if ((month >= 1 && month <= 12)) {
        year = setYearFormat(year);
        month = setMmddFormat(month);
        day = setMmddFormat(day);
      }
      dateArr[1] = year + month + day
    }
    return dateArr.join('')
  }
  else if (cntnt?.length == 16) {
    if (dateArr.length == 1) {
      return dateArr.join('');
    }
    else if (dateArr.length == 5 && dateArr[2].length == 4) { //22.02.11~22.02.24
      resultDate = setYearFormat(dateArr[0]) + setMmddFormat(dateArr[1]) + setMmddFormat(dateArr[2].substr(0, 2))
      resultDate = resultDate + setYearFormat(dateArr[2].substr(2, 4)) + setMmddFormat(dateArr[3]) + setMmddFormat(dateArr[4]);
      return resultDate;
    }
    else return dateArr.join('').substr(0, 16);
  }
  else if (cntnt?.length === 17) {
    if (dateArr.length == 2) {
      return dateArr.join('').substr(0, 16);
    }
    else if (dateArr.length == 6) { //22.02.12-22.02.24
      resultDate = setYearFormat(dateArr[0]) + setMmddFormat(dateArr[1]) + setMmddFormat(dateArr[2])
      resultDate = resultDate + setYearFormat(dateArr[3]) + setMmddFormat(dateArr[4]) + setMmddFormat(dateArr[5]);
      return resultDate;
    }
    else return dateArr.join('');
  }
  else if (cntnt?.length === 20 && dateArr.length == 5) {
    return dateArr?.join('')
  }
  else if (cntnt?.length === 21 && dateArr.length == 6) {
    return dateArr?.join('')
  }
  // else if(cntnt?.length==20){
  //   // if(dateArr.length==6){
  //   //   resultDate = setYearFormat(dateArr[0])+ setMmddFormat(dateArr[1])+setMmddFormat(dateArr[2])
  //   //   resultDate= resultDate+ setYearFormat(dateArr[3])+ setMmddFormat(dateArr[4])+setMmddFormat(dateArr[5]);
  //   // }else return dateArr.join('');
  // }

  const joined = dateArr.join('');
  // Logger.log(joined)
  if (/^\d{16}$/.test(joined)) {
    const from = joined.slice(0, 8);
    const to = joined.slice(8, 16);
    return `${from}${to}`;
  }
  else { //2021-08-10~2021-08-10, 그외..
    Logger.log('🚨🚨🚨 날짜 포멧');
    return dateArr.join('');
  }
}

/**
 * 2024.09.23 루나
 * @param {*} year  
 * @returns 
 */
function setYearFormat(year) {
  let cntntYear = year.substr(0, 2);  // 앞의 두 자리를 연도로 추출
  let monthDay = year.substr(2);      // 나머지 부분은 월과 일로 처리

  // 현재 연도의 마지막 두 자리를 추출
  let currentYear = String(new Date().getFullYear()).substr(2, 2);

  let fullYear = cntntYear <= currentYear ? '20' + cntntYear : '19' + cntntYear;

  return fullYear;
}

/**
 * 2024.09.23 루나
 * @param {*} date 
 * @returns 
 */
function setMmddFormat(date) {
  return date?.length === 1 ? '0' + date : date;
}

function resultFormat(keyObj, extrtId, lvlNo, extrtSno, uppExtrtItmNm, extrtItmNm, extrtRawItmNm, extrtCntnt, itmValCoordVal, itmNmCoordVal, selfRlbtyVal, extrtYn, chartNm) {

  if (Object.keys(keyObj).length < 1) keyObj = { "추출항목": [], "표타이틀": [], "표추출항목": [], "표레이블": [] };

  if (typeof selfRlbtyVal !== 'number') selfRlbtyVal = parseFloat(selfRlbtyVal);
  if (isNaN(selfRlbtyVal)) selfRlbtyVal = 0;

  if (typeof extrtCntnt === 'undefined' || extrtCntnt === 'undefined') extrtCntnt = '';

  let result = {
    img_extc_itnm: extrtItmNm                                           // (String) 추출항목명
    , lvl_no: 1                                                          // (int) 추출레벨번호 
    , extc_itm_no: extrtId                                              // (int) 추출ID - for문 돌릴 때 1부터 +1 증가 (추출 순서)
    , extc_rst_seq: extrtSno                                             // table_content 아니면 모드 0 row에 속해있으면 1, 2, 3 증가
    , hgrk_extc_itm_no: 0                                               // 0으로 고정
    , extc_itm_tpvl: null                                                 // lv 13까지 있는 항목 첫번째
    , extc_rst_cont01: extrtCntnt || ''                                 // (String) 추출내용
    , extc_rst_cont09: ''
    , extc_rst_cont10: ''
    , self_rlbtr_vl: Math.floor(selfRlbtyVal * 100) / 100 || 1.00       // (float) 본인신뢰도값
    , chartNm: chartNm                                                   // (String) 표데이터 표 이름
    // , extrtSno : extrtSno || 0                                        // (int) 추출일련번호
    // , upp_extrtItmNm : uppExtrtItmNm                                  // (String) 상위추출항목명 ex) 본인부담금, 공단부담금, ...
    , extrt_raw_itm_nm: extrtRawItmNm                                   // (String) 추출원본항목명 (detectedLabel)
    , extc_rst_img_crdn_vl : itmValCoordVal || []                        // (String) 항목값좌표값
    // , itm_val_coord_val : itmValCoordVal || []                        // (String) 항목값좌표값
    // , itm_nm_coord_val : itmNmCoordVal || []                          // (String) 항목명좌표값
    , extrtYn: extrtYn || "N"                                           // (String) 추출여부 - 이미지에서 추출 됐으면 Y, 없으면 N
    , acd_ogtdt: ''

  };
  return result;
}



